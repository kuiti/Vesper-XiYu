# core/scheduler.py — APScheduler 定时任务管理
"""替代 asyncio.create_task，支持持久化、错过补执行、错误重试"""
import logging
from core.retry import silent_exc
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import threading

logger = logging.getLogger(__name__)

# 全局调度器实例
_scheduler = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> AsyncIOScheduler:
    """获取全局调度器（懒初始化，线程安全）"""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    with _scheduler_lock:
        if _scheduler is not None:
            return _scheduler
        _scheduler = AsyncIOScheduler(
            job_defaults={
                'coalesce': True,      # 错过的任务合并为一次执行
                'max_instances': 1,     # 同一任务最多1个实例
                'misfire_grace_time': 300,  # 错过5分钟内仍可执行
            }
        )
    return _scheduler


def start_scheduler():
    """启动调度器"""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("[调度器] 已启动")


def shutdown_scheduler():
    """关闭调度器"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[调度器] 已关闭")
    _scheduler = None


def add_interval_job(func, seconds: int, job_id: str = None, **kwargs):
    """添加间隔任务"""
    scheduler = get_scheduler()
    job_id = job_id or f"interval_{func.__name__}"
    try:
        scheduler.add_job(
            func,
            trigger=IntervalTrigger(seconds=seconds),
            id=job_id,
            replace_existing=True,
            **kwargs
        )
        logger.info(f"[调度器] 添加间隔任务: {job_id} (每{seconds}秒)")
    except Exception as e:
        logger.error(f"[调度器] 添加任务失败: {job_id} - {e}")


def add_cron_job(func, hour: int, minute: int = 0, job_id: str = None, **kwargs):
    """添加定时任务（每天指定时间）"""
    scheduler = get_scheduler()
    job_id = job_id or f"cron_{func.__name__}_{hour:02d}{minute:02d}"
    try:
        # 分离 CronTrigger 参数和 add_job 参数
        cron_kwargs = {k: v for k, v in kwargs.items() if k in ('day_of_week', 'day', 'week', 'month', 'year', 'second')}
        job_kwargs = {k: v for k, v in kwargs.items() if k not in cron_kwargs}
        scheduler.add_job(
            func,
            trigger=CronTrigger(hour=hour, minute=minute, **cron_kwargs),
            id=job_id,
            replace_existing=True,
            **job_kwargs
        )
        logger.info(f"[调度器] 添加定时任务: {job_id} ({hour:02d}:{minute:02d})")
    except Exception as e:
        logger.error(f"[调度器] 添加任务失败: {job_id} - {e}")


def remove_job(job_id: str):
    """移除任务"""
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(job_id)
        logger.info(f"[调度器] 移除任务: {job_id}")
    except Exception as e:
        silent_exc("remove_job", e)


def list_jobs() -> list:
    """列出所有任务"""
    scheduler = get_scheduler()
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger),
        }
        for job in scheduler.get_jobs()
    ]


async def _diary_generate_job():
    """AI 日记自动生成任务（23:00 执行）"""
    try:
        from datetime import datetime
        from core.diary_utils import get_today_messages, detect_mood, build_diary_prompt, generate_diary_content
        from core.db import save_diary_entry, get_config

        today = datetime.now().strftime("%Y-%m-%d")
        ai_name = get_config("ai_name", "夕语")
        user_name = get_config("user_name", "用户")

        msg_count, today_msgs, yest_row = get_today_messages()
        if msg_count < 3:
            logger.info(f"[AI日记] 今日消息不足3条({msg_count})，跳过")
            return

        all_text = " ".join(r["content"] for r in today_msgs)
        detected_mood = detect_mood(all_text)
        yesterday_mood = yest_row["mood"] if yest_row else None
        prompt = build_diary_prompt(today, msg_count, today_msgs, ai_name, user_name, yesterday_mood)
        result = generate_diary_content(prompt)

        if result:
            save_diary_entry(today, result, detected_mood)
            logger.info(f"[AI日记] 已生成 {today} 心情:{detected_mood} ({len(result)}字)")
        else:
            logger.warning(f"[AI日记] 生成结果为空，跳过")
    except Exception as e:
        logger.warning(f"[AI日记] 自动生成失败: {e}")


def setup_default_jobs():
    """设置默认的定时任务"""
    # AI 日记：23:00
    add_cron_job(
        _diary_generate_job,
        hour=23,
        job_id="diary_23"
    )

    # 每周清理 emotion_log 和 proactive_response_log（每周日 4:00）
    def _cleanup_job():
        try:
            from core.db import cleanup_emotion_log
            cleanup_emotion_log(90)
        except Exception as e:
            logger.warning(f"[清理] emotion_log 清理失败: {e}")
        try:
            from core.db import get_conn
            from datetime import datetime, timedelta
            cutoff = (datetime.now() - timedelta(days=90)).isoformat()
            with get_conn() as conn:
                conn.cursor().execute("DELETE FROM proactive_response_log WHERE timestamp < ?", (cutoff,))
        except Exception as e:
            logger.warning(f"[清理] proactive_response_log 清理失败: {e}")
    add_cron_job(_cleanup_job, hour=4, day_of_week="sun", job_id="cleanup_emotion_log")

    # 每日 4:30 维护：mention 衰减 + correction/mention 清理（per-character 遍历）
    # 不接的话：mention_weights 3 年后全饱和到 1.0；correction_memory/低权重 mention 无限膨胀
    def _maintenance_job():
        from core.emotion_evolution import _enumerate_character_ids
        from core.mention_tracker import decay_all, cleanup_low_weight
        from core.correction_memory import cleanup_old_corrections
        total_decayed = 0
        total_cleaned = 0
        total_corr = 0
        for cid in _enumerate_character_ids():
            try:
                total_decayed += decay_all(cid)
                total_cleaned += cleanup_low_weight(90, cid)
            except Exception as e:
                logger.warning(f"[维护] 角色{cid} mention 维护失败: {e}")
            try:
                n = cleanup_old_corrections(180, cid)
                total_corr += n
            except Exception as e:
                logger.warning(f"[维护] 角色{cid} correction 清理失败: {e}")
            try:
                from core.memory_provider import batch_extract_memories
                n_mem = batch_extract_memories(cid, max_items=10)
                if n_mem:
                    logger.debug(f"[维护] 角色{cid} 记忆巩固 {n_mem} 条")
            except Exception as e:
                logger.warning(f"[维护] 角色{cid} 记忆巩固失败: {e}")
            try:
                from core.memory_consolidation import consolidate_memories
                result = consolidate_memories(character_id=cid)
                if result and result.get("consolidated", 0) > 0:
                    logger.info(f"[维护] 记忆合并: {result['report']}")
            except Exception as e:
                logger.warning(f"[维护] 记忆合并失败: {e}")
        logger.info(f"[维护] 完成 {len(_enumerate_character_ids())} 个角色: decay={total_decayed} mention_clean={total_cleaned} corr_clean={total_corr}")
    add_cron_job(_maintenance_job, hour=4, minute=30, job_id="daily_maintenance")

    # 每日 3:00 性格演化兜底（即使当天无人发消息也能运行）
    def _evolution_cron():
        try:
            from core.emotion_evolution import process_daily_evolution
            process_daily_evolution()
        except Exception as e:
            logger.warning(f"[性格演化] 定时执行失败: {e}")
    add_cron_job(_evolution_cron, hour=3, minute=0, job_id="daily_evolution")

    logger.info("[调度器] 已设置默认任务: 日记(23点) + 清理(周日4点) + 维护(每日4:30) + 性格演化(3:00)")
