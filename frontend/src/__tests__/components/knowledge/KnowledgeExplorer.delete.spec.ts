import { beforeEach, describe, expect, it, vi } from 'vitest'
import { computed, ref } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import KnowledgeExplorer from '@/components/knowledge/KnowledgeExplorer.vue'
import { useKnowledgeExplorer } from '@/composables/useKnowledgeExplorer'

vi.mock('@/composables/useKnowledgeExplorer', () => ({
  useKnowledgeExplorer: vi.fn(),
}))

const source = {
  id: 7,
  name: 'https://ceylincoworks.com',
  type: 'website',
  agents: [{ id: 'agent-1', name: 'Customer services' }],
  pageStubs: [],
  expanded: false,
  loadingContent: false,
  contentError: null,
  pages: [],
}

const explorer = () => ({
  sources: ref([source]),
  filteredSources: computed(() => [source]),
  queueItems: ref([]),
  error: ref<string | null>(null),
  selectedPageId: ref<string | null>(null),
  selectedSourceId: ref<number | null>(null),
  selectedPage: ref(null),
  selectedSource: ref(null),
  query: ref(''),
  editing: ref(false),
  isAddingPage: ref(false),
  isSaving: ref(false),
  isDeleting: ref(false),
  draftTitle: ref(''),
  draftContent: ref(''),
  draftUrl: ref(''),
  linkPickerOpen: ref(false),
  orgSources: ref([]),
  linkedSourceIds: computed(() => new Set<number>()),
  linkingIds: ref(new Set<number>()),
  isLoadingOrgSources: ref(false),
  orgSourcesError: ref<string | null>(null),
  refresh: vi.fn(),
  startPolling: vi.fn(),
  stopPolling: vi.fn(),
  sourceStatus: vi.fn(() => 'synced'),
  pageRows: vi.fn(() => []),
  toggleSource: vi.fn(),
  selectPage: vi.fn(),
  startAddPage: vi.fn(),
  startEdit: vi.fn(),
  savePage: vi.fn(),
  cancelEdit: vi.fn(),
  deletePage: vi.fn(),
  deleteSource: vi.fn(async () => undefined),
  openLinkPicker: vi.fn(),
  linkSource: vi.fn(),
  unlinkSource: vi.fn(async () => undefined),
  submitSource: vi.fn(),
})

describe('KnowledgeExplorer agent delete', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fully deletes a source instead of only unlinking it', async () => {
    const ex = explorer()
    vi.mocked(useKnowledgeExplorer).mockReturnValue(ex as any)
    const wrapper = shallowMount(KnowledgeExplorer, {
      props: {
        mode: 'agent',
        organizationId: 'org-1',
        agentId: 'agent-1',
      },
    })

    wrapper.findComponent({ name: 'KnowledgeSourceTree' }).vm.$emit('delete-source', source)
    await flushPromises()

    expect(wrapper.text()).toContain('links to every agent')
    await wrapper.get('button.btn--danger-solid').trigger('click')
    await flushPromises()

    expect(ex.deleteSource).toHaveBeenCalledWith(source)
    expect(ex.unlinkSource).not.toHaveBeenCalled()
  })
})
