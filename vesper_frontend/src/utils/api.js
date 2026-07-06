const BASE = ''

async function get(p) { const r = await fetch(BASE + p); if (!r.ok) throw Error(r.status); return r.json() }
async function post(p, b) { const r = await fetch(BASE + p, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(b) }); if (!r.ok) throw Error(r.status); return r.json() }
async function del(p) { const r = await fetch(BASE + p, { method:'DELETE' }); if (!r.ok) throw Error(r.status); return r.json() }

export const fetchCharacters = () => get('/characters/')
export const fetchActiveCharacter = () => get('/characters/active')
export const activateCharacter = (id) => post(`/characters/activate/${id}`)
export const deactivateCharacter = () => post('/characters/deactivate')
export const createCharacter = (d) => post('/characters/', d)
export const deleteCharacter = (id) => del(`/characters/${id}`)
export const updateCharacter = (id, d) => post(`/characters/${id}`, d)
export const fetchSettings = () => get('/settings/')
export const updateSetting = (k, v) => post('/settings/', { key: k, value: v })
export const fetchEmotion = () => get('/emotion/relationship')
export const uploadAvatar = async (role, file) => { const f = new FormData(); f.append('file', file); const r = await fetch(`/avatar/upload/${role}`, { method:'POST', body:f }); return r.json() }
export const fetchStats = () => get('/stats/overview')
export const sendFeedback = (msgId, score) => post('/feedback', { msg_id: msgId, score })
export const fetchRelationship = () => get('/emotion/relationship')
export const fetchHistory = (limit=40, afterId=null) => { const p = new URLSearchParams({ limit }); if (afterId) p.set('after_id', afterId); return get(`/chat/history/?${p}`) }
export const toggleFavorite = (msgId) => post(`/favorites/${msgId}`)
export const deleteFavorite = (msgId) => del(`/favorites/${msgId}`)
export const fetchFavorites = () => get('/favorites/')
