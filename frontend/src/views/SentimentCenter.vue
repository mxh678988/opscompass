<template>
  <div class="sentiment-page">
    <h1>舆情监控</h1>
    <p>Plugin ID: {{ pluginId }}</p>
    <p>Plugin Version: {{ pluginVersion }}</p>
    <p>Plugin Namespace: {{ namespace }}</p>

    <div class="actions">
      <button @click="loadTopics">加载主题</button>
      <button @click="createTopic">创建主题</button>
    </div>

    <div class="topics">
      <h3>监测主题</h3>
      <ul v-if="topics.length">
        <li v-for="topic in topics" :key="topic.id">
          <strong>{{ topic.name }}</strong>
          <span>{{ topic.keywords.join(', ') }}</span>
        </li>
      </ul>
      <p v-else>暂无主题</p>
    </div>

    <div class="analytics" v-if="analytics">
      <h3>分析报告</h3>
      <p>正面: {{ analytics.positive }} | 中性: {{ analytics.neutral }} | 负面: {{ analytics.negative }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const pluginId = 'sentiment'
const pluginVersion = '0.12.0'
const namespace = 'com.laomeng.opp.ner'

const topics = ref([])
const analytics = ref(null)

const loadTopics = async () => {
  try {
    const result = await window.opsCompass?.send?.({
      plugin_id: pluginId,
      action: 'get_topics',
    })
    if (result && result.data) {
      topics.value = result.data
    }
  } catch (e) {
    console.error('加载主题失败:', e)
  }
}

const createTopic = async () => {
  try {
    const result = await window.opsCompass?.send?.({
      plugin_id: pluginId,
      action: 'create_topic',
      params: {
        name: '新主题',
        keywords: ['AI', '运营'],
      },
    })
    if (result && result.data) {
      topics.value.push(result.data)
    }
  } catch (e) {
    console.error('创建主题失败:', e)
  }
}

onMounted(() => {
  loadTopics()
})
</script>

<style scoped>
.sentiment-page {
  padding: 20px;
}

.actions {
  margin: 16px 0;
}

.actions button {
  margin-right: 8px;
  padding: 8px 16px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #f5f5f5;
  cursor: pointer;
}

.actions button:hover {
  background: #e8e8e8;
}

.topics ul {
  list-style: none;
  padding: 0;
}

.topics li {
  padding: 8px 0;
  border-bottom: 1px solid #eee;
}

.topics li span {
  color: #666;
  margin-left: 8px;
}
</style>
