import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatSettings from '../components/settings/ChatSettings.vue'

describe('ChatSettings', () => {
  it('renders with default props', () => {
    const wrapper = mount(ChatSettings, {
      props: {
        chatFontSize: 14,
        sentenceMode: 'auto',
        proactiveFreq: 'medium',
        proactiveStyle: 'warm',
        relMode: 'fast',
        quickPhrases: ['你好', '再见'],
      },
    })
    expect(wrapper.find('.sc-pane').exists()).toBe(true)
    expect(wrapper.findAll('.card').length).toBeGreaterThanOrEqual(5)
  })

  it('displays quick phrases', () => {
    const wrapper = mount(ChatSettings, {
      props: {
        chatFontSize: 14,
        sentenceMode: 'auto',
        proactiveFreq: 'medium',
        proactiveStyle: 'warm',
        relMode: 'fast',
        quickPhrases: ['你好', '再见'],
      },
    })
    const inputs = wrapper.findAll('.phrase-row input')
    expect(inputs).toHaveLength(2)
  })

  it('emits add-phrase on button click', async () => {
    const wrapper = mount(ChatSettings, {
      props: {
        chatFontSize: 14,
        sentenceMode: 'auto',
        proactiveFreq: 'medium',
        proactiveStyle: 'warm',
        relMode: 'fast',
        quickPhrases: [],
      },
    })
    await wrapper.find('button.btn-s').trigger('click')
    expect(wrapper.emitted('add-phrase')).toBeTruthy()
  })
})