import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import AISetup from '@/components/ai/AISetup.vue'
import { useAISetup } from '@/composables/useAISetup'

vi.mock('@/composables/useAISetup', () => ({
  useAISetup: vi.fn(),
}))

vi.mock('@/composables/useEnterpriseFeatures', () => ({
  useEnterpriseFeatures: () => ({
    hasEnterpriseModule: false,
    moduleImports: {},
    loadModule: vi.fn(),
  }),
}))

vi.mock('@/utils/storage', () => ({
  useSubscriptionStorage: () => ({
    getCurrentSubscription: () => null,
    isSubscriptionActive: () => false,
    hasFeature: () => false,
    getAvailablePlans: () => [],
  }),
}))

const mockSetup = (hasStoredApiKey: boolean) => {
  vi.mocked(useAISetup).mockReturnValue({
    isLoading: ref(false),
    error: ref(''),
    providers: ref([{
      value: 'groq',
      label: 'Groq',
      requires_api_key: true,
      custom_allowed: true,
      api_key_url: 'https://console.groq.com/keys',
      models: [{ value: 'openai/gpt-oss-120b', label: 'GPT-OSS 120B' }],
    }]),
    setupConfig: ref({
      provider: 'groq',
      model: 'openai/gpt-oss-120b',
      apiKey: '',
    }),
    saveAISetup: vi.fn(async () => true),
    updateAISetup: vi.fn(async () => true),
    loadProviders: vi.fn(),
    loadExistingConfig: vi.fn(),
    hasExistingConfig: ref(hasStoredApiKey),
    hasStoredApiKey: ref(hasStoredApiKey),
  })
}

describe('AISetup API key masking', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows a masked placeholder without returning the saved tenant secret', () => {
    mockSetup(true)
    const wrapper = mount(AISetup)
    const input = wrapper.get<HTMLInputElement>('#apiKey')

    expect(input.element.value).toBe('')
    expect(input.attributes('placeholder')).toBe('••••••••••••••••')
    expect(input.attributes('required')).toBeUndefined()
    expect(wrapper.text()).toContain('A key is saved securely for this workspace')
  })

  it('requires a key when the tenant has no stored credential', () => {
    mockSetup(false)
    const wrapper = mount(AISetup)
    const input = wrapper.get('#apiKey')

    expect(input.attributes('placeholder')).toBe('Enter your API key')
    expect(input.attributes('required')).toBeDefined()
  })
})
