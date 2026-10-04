export type Ctx = { tokens: number; window: number; percent: number }
export type Part = { name: string; tokens: number }
export type Limit = { kind: string; percentUsed: number; resetsAt?: string }

declare module 'claude-code' {
  interface PluginState {
    'elizabeth-progress': {
      ctx: Ctx | null
      parts: Part[]
      limits: Limit[]
      cost: number | null
      hist: number[]
      compactAt: number | null
    }
  }
}
