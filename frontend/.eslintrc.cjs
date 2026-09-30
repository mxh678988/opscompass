/* OpsCompass 前端 lint 基线（eslint 8 + Vue 3 + TypeScript）
 * 基线策略：先以“推荐规则 + 少量无争议 error”落地，纳入 CI 第 8 项，
 * 后续版本再逐步收紧（见 docs/changelog.md [Unreleased]）。
 */
module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
    node: true,
  },
  extends: [
    'eslint:recommended',
    // 只取 vue3 正确性规则集；格式类规则交给 prettier（npm run format），避免双重标准
    'plugin:vue/vue3-essential',
    'plugin:@typescript-eslint/recommended',
  ],
  parser: 'vue-eslint-parser',
  parserOptions: {
    parser: '@typescript-eslint/parser',
    ecmaVersion: 2022,
    sourceType: 'module',
  },
  plugins: ['vue', '@typescript-eslint'],
  rules: {
    // 基线保持宽松，避免历史代码一次性产生大量噪音；仅为明确无争议项置 error
    'no-debugger': 'error',
    'no-console': 'off',
    'vue/multi-word-component-names': 'off',
    '@typescript-eslint/no-explicit-any': 'warn',
    '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
  },
  ignorePatterns: ['dist/', 'node_modules/', '*.d.ts', 'vite.config.*'],
};
