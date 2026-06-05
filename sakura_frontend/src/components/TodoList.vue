<template>
  <div class="todo-list">
    <div class="add-todo">
      <input v-model="newTodo" @keyup.enter="addTodo" placeholder="新待办...">
      <button @click="addTodo">+</button>
    </div>
    <div class="items">
      <div v-for="todo in todos" :key="todo.id" class="todo-item">
        <input type="checkbox" :checked="todo.done" @change="toggleTodo(todo.id, todo)">
        <span :class="{ done: todo.done }">{{ todo.task }}</span>
        <button @click="deleteTodo(todo.id)" class="del-btn">删除</button>
      </div>
      <div v-if="!todos.length" class="empty">还没待办。试试输入「买菜」然后按 +</div>
    </div>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  data() {
    return {
      todos: [],
      newTodo: ''
    }
  },
  mounted() {
    this.loadTodos()
  },
  methods: {
    async loadTodos() {
      try {
        const res = await api.get('/todos/')
        this.todos = res.data
      } catch (err) {
        console.error('加载待办失败', err)
      }
    },
    async addTodo() {
      if (!this.newTodo.trim()) return
      try {
        await api.post('/todos/', { task: this.newTodo })
        this.newTodo = ''
        await this.loadTodos()
      } catch (err) {
        console.error('添加待办失败', err)
      }
    },
    async toggleTodo(id, todo) {
      try {
        await api.patch(`/todos/${id}`, { done: !todo.done })
        await this.loadTodos()
      } catch (err) {
        console.error('更新待办失败', err)
      }
    },
    async deleteTodo(id) {
      try {
        await api.delete(`/todos/${id}`)
        await this.loadTodos()
      } catch (err) {
        console.error('删除待办失败', err)
      }
    }
  }
}
</script>

<style scoped>
.todo-list { padding: 10px; }
.add-todo { display: flex; gap: 8px; margin-bottom: 12px; }
.add-todo input { flex: 1; padding: 6px; border-radius: 8px; border: 1px solid var(--border); background: var(--bg); color: var(--tc); }
.add-todo button { background: var(--p); border: none; border-radius: 8px; color: #fff; cursor: pointer; width: 32px; }
.todo-item { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; padding: 8px 10px; background: var(--sb); border-radius: 8px; transition: transform .15s, background .15s; }
.todo-item:hover { background: rgba(255,255,255,.04); transform: translateX(2px); }
.todo-item input[type="checkbox"] { accent-color: var(--p, #e8929b); width: 16px; height: 16px; cursor: pointer; }
.todo-item span { flex: 1; color: var(--tc); }
.todo-item span.done { text-decoration: line-through; color: var(--tc2); transition: all .25s; }
.todo-item button { background: none; border: none; cursor: pointer; font-size: 14px; opacity: .4; transition: opacity .15s; }
.todo-item button:hover { opacity: 1; }
.empty { color: var(--tc2); text-align: center; font-size: 14px; padding: 20px; }
</style>