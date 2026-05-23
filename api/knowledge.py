from fastapi import APIRouter, UploadFile, File, Form
from core.db import add_document, get_documents, delete_document, get_conn
from core.vector_store import chunk_text, add_document_vectors, delete_document_vectors, is_model_ready
import os

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

UPLOAD_DIR = os.path.join("data", "knowledge")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}


def _read_file(filepath: str, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()


@router.post("/upload")
async def upload_knowledge(file: UploadFile = File(...)):
    if not file.filename:
        return {"status": "error", "message": "未选择文件"}
    safe_name = os.path.basename(file.filename)
    if not safe_name or safe_name.startswith('.') or safe_name != file.filename:
        return {"status": "error", "message": "文件名不合法"}
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return {"status": "error", "message": f"不支持的文件类型: {ext}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}"}

    filepath = os.path.join(UPLOAD_DIR, safe_name)
    total_bytes = 0
    MAX_SIZE = 50 * 1024 * 1024  # 50MB
    try:
        with open(filepath, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_SIZE:
                    os.remove(filepath)
                    return {"status": "error", "message": "文件大小不能超过50MB"}
                f.write(chunk)
    except Exception as e:
        return {"status": "error", "message": f"文件保存失败: {str(e)}"}

    try:
        text = _read_file(filepath, file.filename)
    except Exception as e:
        return {"status": "error", "message": f"文件读取失败: {str(e)}"}

    if not text or not text.strip():
        return {"status": "error", "message": "文件内容为空"}

    size = os.path.getsize(filepath)
    chunks = chunk_text(text)
    doc_id = add_document(file.filename, len(chunks), size)

    if is_model_ready():
        count = add_document_vectors(doc_id, chunks, file.filename)
    else:
        count = 0

    return {"status": "ok", "id": doc_id, "filename": file.filename, "chunks": len(chunks), "indexed": count}


@router.get("/")
async def list_knowledge():
    docs = get_documents()
    return {"documents": docs, "model_ready": is_model_ready()}


@router.delete("/{doc_id}")
async def remove_knowledge(doc_id: int):
    # 先查文件名再删记录
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT filename FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
    if row:
        filepath = os.path.join(UPLOAD_DIR, row["filename"])
        try:
            os.remove(filepath)
        except Exception as e:
            print(f"[知识库] 删除文件失败: {e}")
    delete_document(doc_id)
    delete_document_vectors(doc_id)
    return {"status": "ok"}
