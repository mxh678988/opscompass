<script setup lang="ts">
// 登录页：账号密码登录，成功后按 redirect 参数跳回原页面
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/store/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

function resolveRedirect(): string {
  const raw = route.query.redirect
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' && value.startsWith('/') ? value : '/'
}

async function onSubmit() {
  if (!form.username.trim() || !form.password) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await auth.login(form.username.trim(), form.password)
    await router.replace(resolveRedirect())
  } catch (e) {
    error.value = (e as Error).message || '登录失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <form class="login-card" @submit.prevent="onSubmit">
      <img class="brand-logo" src="/favicon.ico" alt="运营智脑" />
      <h1 class="brand">运营智脑</h1>
      <p class="slogan">让数据自动做出最优决策</p>
      <p class="subtitle">多租户运营数据智能决策平台</p>

      <label class="field">
        <span class="label">用户名</span>
        <input
          v-model="form.username"
          type="text"
          autocomplete="username"
          placeholder="请输入用户名"
          :disabled="loading"
        />
      </label>

      <label class="field">
        <span class="label">密码</span>
        <input
          v-model="form.password"
          type="password"
          autocomplete="current-password"
          placeholder="请输入密码"
          :disabled="loading"
        />
      </label>

      <p v-if="error" class="error">{{ error }}</p>

      <button class="submit" type="submit" :disabled="loading">
        {{ loading ? '登录中…' : '登 录' }}
      </button>

      <p class="hint">首次部署请使用 .env 中 SECURITY_ADMIN_USERNAME / SECURITY_ADMIN_PASSWORD，登录后请立即修改密码。</p>
    </form>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background:
    radial-gradient(ellipse at 20% 50%, rgba(37, 99, 235, 0.06) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 20%, rgba(147, 197, 253, 0.08) 0%, transparent 45%),
    radial-gradient(ellipse at 60% 80%, rgba(74, 222, 128, 0.05) 0%, transparent 40%),
    linear-gradient(160deg, #f0f4ff 0%, #fafbff 40%, #f5faf5 70%, #fefefe 100%);
}

.login-card {
  width: 380px;
  padding: 36px 32px 28px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow:
    0 4px 6px rgba(0, 0, 0, 0.04),
    0 12px 32px rgba(31, 41, 55, 0.08);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.brand-logo {
  display: block;
  width: 48px;
  height: 48px;
  margin: 0 auto;
}

.brand {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--color-text);
  text-align: center;
}

.slogan {
  margin: -4px 0 0;
  font-size: 12px;
  letter-spacing: 0.5px;
  color: var(--color-primary);
  text-align: center;
}

.subtitle {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--color-text-muted);
  text-align: center;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.label {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.field input {
  height: 40px;
  padding: 0 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--color-text);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.field input:focus {
  border-color: var(--color-focus);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.field input:disabled {
  background: var(--color-bg-subtle);
  cursor: not-allowed;
}

.error {
  margin: 0;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--color-error-light);
  border: 1px solid var(--color-error-border);
  color: var(--color-error);
  font-size: 13px;
  line-height: 1.4;
}

.submit {
  display: block;
  width: 100%;
  height: 42px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 1px;
  cursor: pointer;
  transition: background var(--transition-fast), box-shadow var(--transition-fast);
}

.submit:hover:not(:disabled) {
  background: var(--color-primary-hover);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
}

.submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-text-muted);
  text-align: center;
}

/* ===== 响应式自适应 ===== */
.login-page {
  padding: 24px 16px;
}

.login-card {
  width: 380px;
  max-width: 100%;
}

@media (max-width: 768px) {
  .login-page {
    padding: 20px 16px;
  }
}

@media (max-width: 480px) {
  .login-page {
    padding: 16px 12px;
  }
  .login-card {
    padding: 26px 20px 22px;
    gap: 14px;
  }
  .brand {
    font-size: 20px;
  }
}
</style>
