<script setup lang="ts">
/**
 * Next Best Action 行动卡：给出“接下来最该做什么”的决策建议
 * level 决定优先级视觉：high=红点 / mid=黄点 / low=灰点
 */
withDefaults(
  defineProps<{
    title?: string
    actions: Array<{
      id: string
      title: string
      desc?: string
      level?: 'high' | 'mid' | 'low'
      link?: string
    }>
  }>(),
  { title: '下一步行动', actions: () => [] },
)
</script>

<template>
  <section class="nba-card" aria-label="Next Best Action">
    <header class="head">
      <h2>{{ title }}</h2>
      <span class="hint">Next Best Action</span>
    </header>
    <div v-if="!actions.length" class="empty-hint">暂无待办行动，运营状态良好</div>
    <ul class="list">
      <li v-for="a in actions" :key="a.id" class="item" :class="`lv-${a.level ?? 'low'}`">
        <span class="dot" aria-hidden="true" />
        <div class="body">
          <p class="title">{{ a.title }}</p>
          <p v-if="a.desc" class="desc">{{ a.desc }}</p>
        </div>
        <router-link v-if="a.link" :to="a.link" class="go">去处理 →</router-link>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.nba-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--color-primary-light) 0%, var(--bg-surface) 42%);
  padding: 20px;
  margin-bottom: 24px;
}
.head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.head h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
}
.hint {
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  border: 1px solid var(--color-border-light);
  transition: border-color var(--transition-fast);
}
.item:hover {
  border-color: var(--color-primary-border);
}
.dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
}
.lv-high .dot {
  background: var(--color-error);
  box-shadow: 0 0 0 3px var(--color-error-light);
}
.lv-mid .dot {
  background: var(--color-warning);
  box-shadow: 0 0 0 3px var(--color-warning-light);
}
.lv-low .dot {
  background: var(--color-text-muted);
}
.body {
  flex: 1;
  min-width: 0;
}
.title {
  margin: 0;
  font-size: 13.5px;
  font-weight: 500;
  color: var(--color-text);
}
.desc {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.go {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--color-primary);
  text-decoration: none;
  white-space: nowrap;
}
.empty-hint {
  font-size: 13px;
  color: var(--color-text-muted);
  padding: 8px 0 2px;
}
</style>
