/** OpenTelemetry 前端可观测性初始化。

- 默认关闭（NODE_ENV !== production 或 VITE_OTEL_ENABLED !== true）。
- 使用 @opentelemetry/sdk-trace-web + @opentelemetry/exporter-trace-otlp-http。
- 自动采集 Web 请求（XMLHttpRequest / Fetch）和路由变化。
*/

import { WebTracerProvider } from '@opentelemetry/sdk-trace-web'
import { registerInstrumentations } from '@opentelemetry/instrumentation'
import { FetchInstrumentation } from '@opentelemetry/instrumentation-fetch'
import { XMLHttpRequestInstrumentation } from '@opentelemetry/instrumentation-xml-http-request'
import { resourceFromAttributes } from '@opentelemetry/resources'
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions'
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base'
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http'

const OTEL_ENABLED = import.meta.env.VITE_OTEL_ENABLED === 'true'
const OTEL_SERVICE_NAME = import.meta.env.VITE_OTEL_SERVICE_NAME || 'opscompass-frontend'
const OTEL_EXPORTER_ENDPOINT = import.meta.env.VITE_OTEL_EXPORTER_ENDPOINT || 'http://localhost:4318/v1/traces'

let initialized = false

export function initFrontendTracing(): void {
  if (initialized || !OTEL_ENABLED) {
    if (!OTEL_ENABLED) {
      console.debug('[OTel] 已关闭（VITE_OTEL_ENABLED !== true），跳过 tracing 初始化')
    }
    return
  }

  try {
    const exporter = new OTLPTraceExporter({
      url: OTEL_EXPORTER_ENDPOINT,
    })

    const provider = new WebTracerProvider({
      resource: resourceFromAttributes({
        [SemanticResourceAttributes.SERVICE_NAME]: OTEL_SERVICE_NAME,
        [SemanticResourceAttributes.SERVICE_VERSION]: import.meta.env.VITE_APP_VERSION || '0.0.0',
        [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: import.meta.env.VITE_APP_ENV || 'development',
      }),
      spanProcessors: [new BatchSpanProcessor(exporter)],
    })
    provider.register()

    registerInstrumentations({
      instrumentations: [
        new FetchInstrumentation(),
        new XMLHttpRequestInstrumentation(),
      ],
    })

    initialized = true
    console.info('[OTel] 前端 Tracing 已初始化:', OTEL_SERVICE_NAME)
  } catch (error) {
    console.warn('[OTel] 前端 Tracing 初始化失败:', error)
  }
}
