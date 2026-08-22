import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AgentInstructionsTab from '@/components/agent/AgentInstructionsTab.vue'
import { agentService } from '@/services/agent'

vi.mock('@/services/agent', () => ({
  agentService: {
    getGuardrailDefault: vi.fn(async () => 'Answer only about CeylincoWorks.'),
  },
}))

vi.mock('@/composables/useAgentEdit', () => ({
  useAgentEdit: () => ({
    generateInstructions: vi.fn(),
    isLoading: false,
    error: null,
  }),
}))

vi.mock('@/composables/useEnterpriseFeatures', () => ({
  useEnterpriseFeatures: () => ({ hasEnterpriseModule: false }),
}))

vi.mock('@/utils/storage', () => ({
  useSubscriptionStorage: () => ({
    isSubscriptionActive: () => true,
    hasFeature: () => true,
  }),
}))

const mountTab = () => mount(AgentInstructionsTab, {
  props: {
    instructions: 'Be helpful.',
    businessName: 'CeylincoWorks',
    businessDomain: 'ceylincoworks.com',
    guardrailPrompt: null,
    guardrailEnabled: true,
    transferToHuman: false,
    aiRepliesEnabled: true,
    askForRating: false,
    handoffCollectEmail: true,
    handoffCollectName: true,
    userGroups: [],
    selectedGroupIds: [],
    loadingGroups: false,
    isEditing: true,
    agent: { id: 'agent-123' },
  },
  global: {
    stubs: {
      FontAwesomeIcon: true,
      RouterLink: true,
    },
    directives: {
      tooltip: () => undefined,
    },
  },
})

describe('AgentInstructionsTab business identity', () => {
  beforeEach(() => vi.clearAllMocks())

  it('loads the default guardrail for the current agent', async () => {
    mountTab()
    await flushPromises()
    expect(agentService.getGuardrailDefault).toHaveBeenCalledWith('agent-123')
  })

  it('saves the agent business name and domain', async () => {
    const wrapper = mountTab()
    await flushPromises()

    await wrapper.get('button.save-button').trigger('click')

    expect(wrapper.emitted('save-agent')?.[0]?.[0]).toMatchObject({
      businessName: 'CeylincoWorks',
      businessDomain: 'ceylincoworks.com',
    })
  })
})
