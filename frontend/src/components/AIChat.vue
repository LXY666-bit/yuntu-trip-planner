<template>
  <div class="ai-chat-floating" :class="{ 'chat-is-open': chatOpen }">
    <div class="container-ai-input">
      <div v-for="index in 15" :key="`chat-area-${index}`" class="area"></div>
      <div class="container-wrap" :class="{ open: chatOpen }">
        <div class="card">
          <div class="background-blur-balls">
            <div class="balls">
              <span class="ball rosa"></span>
              <span class="ball violet"></span>
              <span class="ball green"></span>
              <span class="ball cyan"></span>
            </div>
          </div>
          <div class="content-card" :class="{ clickable: !chatOpen }" @click="openChatPanel">
            <div class="background-blur-card">
              <div class="eyes">
                <span class="eye"></span>
                <span class="eye"></span>
              </div>
              <div class="eyes happy">
                <svg fill="none" viewBox="0 0 24 24">
                  <path fill="currentColor" d="M8.28386 16.2843C8.9917 15.7665 9.8765 14.731 12 14.731C14.1235 14.731 15.0083 15.7665 15.7161 16.2843C17.8397 17.8376 18.7542 16.4845 18.9014 15.7665C19.4323 13.1777 17.6627 11.1066 17.3088 10.5888C16.3844 9.23666 14.1235 8 12 8C9.87648 8 7.61556 9.23666 6.69122 10.5888C6.33728 11.1066 4.56771 13.1777 5.09858 15.7665C5.24582 16.4845 6.16034 17.8376 8.28386 16.2843Z"></path>
                </svg>
                <svg fill="none" viewBox="0 0 24 24">
                  <path fill="currentColor" d="M8.28386 16.2843C8.9917 15.7665 9.8765 14.731 12 14.731C14.1235 14.731 15.0083 15.7665 15.7161 16.2843C17.8397 17.8376 18.7542 16.4845 18.9014 15.7665C19.4323 13.1777 17.6627 11.1066 17.3088 10.5888C16.3844 9.23666 14.1235 8 12 8C9.87648 8 7.61556 9.23666 6.69122 10.5888C6.33728 11.1066 4.56771 13.1777 5.09858 15.7665C5.24582 16.4845 6.16034 17.8376 8.28386 16.2843Z"></path>
                </svg>
              </div>
            </div>
          </div>
          <div class="container-ai-chat" @click.stop>
            <button type="button" class="chat-close-btn" @click.stop="closeChatPanel">×</button>
            <div class="chat">
              <div class="chat-bot">
                <div class="chat-history" ref="chatMessagesRef">
                  <div v-if="chatHistory.length === 0" class="chat-empty">
                    <p>你好！我是你的旅行管家，可以向我提问行程相关的问题~</p>
                    <div class="chat-suggestions">
                      <button
                        v-for="question in quickQuestions"
                        :key="question.label"
                        type="button"
                        class="chat-suggestion"
                        :disabled="chatLoading || !tripPlan"
                        @click="sendQuickQuestion(question.question)"
                      >
                        {{ question.label }}
                      </button>
                    </div>
                  </div>
                  <div
                    v-for="(msg, idx) in chatHistory"
                    :key="`chat-${idx}`"
                    class="chat-msg"
                    :class="msg.role"
                  >
                    {{ msg.content }}
                  </div>
                  <div v-if="chatLoading" class="chat-msg assistant typing">
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                  </div>
                </div>
                <textarea
                  v-model="chatInput"
                  :placeholder="chatPlaceholder"
                  name="chat_bot"
                  id="chat_bot"
                  :disabled="chatLoading || !tripPlan"
                  @keydown.enter.exact.prevent="sendChatMessage"
                ></textarea>
              </div>
              <div class="options">
                <div class="btns-add">
                  <button type="button" disabled>
                    <svg viewBox="0 0 24 24" height="20" width="20" xmlns="http://www.w3.org/2000/svg">
                      <path d="M7 8v8a5 5 0 1 0 10 0V6.5a3.5 3.5 0 1 0-7 0V15a2 2 0 0 0 4 0V8" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" stroke="currentColor" fill="none"></path>
                    </svg>
                  </button>
                </div>
                <button
                  type="button"
                  class="btn-submit"
                  :disabled="chatLoading || !chatInput.trim() || !tripPlan"
                  @click="sendChatMessage"
                >
                  <i>
                    <svg viewBox="0 0 512 512">
                      <path d="M473 39.05a24 24 0 0 0-25.5-5.46L47.47 185h-.08a24 24 0 0 0 1 45.16l.41.13l137.3 58.63a16 16 0 0 0 15.54-3.59L422 80a7.07 7.07 0 0 1 10 10L226.66 310.26a16 16 0 0 0-3.59 15.54l58.65 137.38c.06.2.12.38.19.57c3.2 9.27 11.3 15.81 21.09 16.25h1a24.63 24.63 0 0 0 23-15.46L478.39 64.62A24 24 0 0 0 473 39.05" fill="currentColor"></path>
                    </svg>
                  </i>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import axios from 'axios'
import type { ChatMessage, TripPlan } from '@/types'

const props = defineProps<{
  tripPlan: TripPlan | null
}>()

const chatOpen = ref(false)
const chatInput = ref('')
const chatHistory = ref<ChatMessage[]>([])
const chatLoading = ref(false)
const chatMessagesRef = ref<HTMLElement | null>(null)

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const quickQuestions = [
  { label: '费用是多少？', question: '这次旅行的总费用大概是多少？各项花费分别多少？' },
  { label: '适合孩子吗？', question: '这个行程适合带小孩/老人吗？' },
  { label: '美食推荐？', question: '行程中有什么特别推荐的美食吗？' },
]

const chatPlaceholder = computed(() => {
  if (!props.tripPlan) return '暂无行程数据'
  return '输入你的问题，比如"第二天穿什么？"'
})

const scrollChatToBottom = () => {
  nextTick(() => {
    if (chatMessagesRef.value) {
      chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
    }
  })
}

watch(chatOpen, (open) => {
  if (open) scrollChatToBottom()
})

const openChatPanel = () => {
  if (!chatOpen.value) {
    chatOpen.value = true
  }
}

const closeChatPanel = () => {
  chatOpen.value = false
}

const sendQuickQuestion = (q: string) => {
  chatInput.value = q
  void sendChatMessage()
}

const sendChatMessage = async () => {
  const text = chatInput.value.trim()
  if (!text || chatLoading.value || !props.tripPlan) return

  chatHistory.value.push({ role: 'user', content: text })
  chatInput.value = ''
  chatLoading.value = true
  scrollChatToBottom()

  try {
    const res = await axios.post(`${apiBaseUrl}/api/chat/ask`, {
      message: text,
      trip_plan: props.tripPlan,
      history: chatHistory.value.slice(0, -1),
    })

    if (res.data.success) {
      chatHistory.value.push({ role: 'assistant', content: res.data.reply })
    } else {
      chatHistory.value.push({ role: 'assistant', content: '抱歉，暂时无法回答，请稍后重试。' })
    }
  } catch (err) {
    console.error('Chat error:', err)
    chatHistory.value.push({ role: 'assistant', content: '网络连接异常，请稍后重试。' })
  } finally {
    chatLoading.value = false
    scrollChatToBottom()
  }
}
</script>

<style scoped lang="scss">
.ai-chat-floating {
  position: fixed;
  left: 24px;
  bottom: 24px;
  z-index: 1000;
  transform: scale(0.3);
  transform-origin: left bottom;
  transition: all 0.4s ease;
}

.ai-chat-floating.chat-is-open {
  left: 50%;
  top: 100%;
  transform: translate(-50%, -100%) scale(1);
  transform-origin: center center;
}

.container-ai-input {
  --perspective: 1000px;
  --translateY: 45px;
  position: absolute;
  inset: 0;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  transform-style: preserve-3d;
  pointer-events: none;
}

.area {
  pointer-events: none;
}

.container-wrap {
  display: flex;
  align-items: center;
  justify-items: center;
  position: absolute;
  left: 0;
  bottom: 0;
  z-index: 9;
  transform-style: preserve-3d;
  cursor: default;
  padding: 4px;
  transition: all 0.3s ease;
  pointer-events: auto;
}

.container-wrap:hover {
  padding: 0;
}

.container-wrap:active {
  transform: scale(0.95);
}

.container-wrap:after {
  content: "";
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translateX(-50%) translateY(-55%);
  width: 12rem;
  height: 11rem;
  background-color: #dedfe0;
  border-radius: 2rem;
  transition: all 0.3s ease;
}

.container-wrap:hover:after {
  transform: translateX(-50%) translateY(-50%);
  height: 10rem;
}

.container-wrap.open .eyes {
  opacity: 0;
}

.container-wrap.open .content-card {
  width: 500px;
  height: 620px;
}

.container-wrap.open .background-blur-balls {
  border-radius: 24px;
}

.container-wrap.open .container-ai-chat {
  opacity: 1;
  visibility: visible;
  z-index: 99999;
  pointer-events: auto;
}

.card {
  width: 100%;
  height: 100%;
  position: relative;
  transform-style: preserve-3d;
  will-change: transform;
  transition: all 0.6s ease;
  border-radius: 3rem;
  display: flex;
  align-items: flex-end;
  transform: translateZ(50px);
  justify-content: flex-start;
}

.background-blur-balls {
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  z-index: -10;
  border-radius: 3rem;
  transition: all 0.3s ease;
  background-color: rgba(255, 255, 255, 0.8);
  overflow: hidden;
}

.balls {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translateX(-50%) translateY(-50%);
  animation: rotate-background-balls 10s linear infinite;
}

.container-wrap:hover .balls {
  animation-play-state: paused;
}

.ball {
  width: 6rem;
  height: 6rem;
  position: absolute;
  border-radius: 50%;
  filter: blur(30px);
}

.ball.violet { top: 0; left: 50%; transform: translateX(-50%); background-color: #9147ff; }
.ball.green { bottom: 0; left: 50%; transform: translateX(-50%); background-color: #34d399; }
.ball.rosa { top: 50%; left: 0; transform: translateY(-50%); background-color: #ec4899; }
.ball.cyan { top: 50%; right: 0; transform: translateY(-50%); background-color: #05e0f5; }

.content-card {
  width: 12rem;
  height: 12rem;
  display: flex;
  border-radius: 3rem;
  transition: all 0.3s ease;
  overflow: hidden;
}

.content-card.clickable { cursor: pointer; }

.background-blur-card {
  width: 100%;
  height: 100%;
  backdrop-filter: blur(50px);
}

.eyes {
  position: absolute;
  left: 50%;
  bottom: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  height: 52px;
  gap: 2rem;
  transition: all 0.3s ease;

  .eye {
    width: 26px;
    height: 52px;
    background-color: #fff;
    border-radius: 16px;
    animation: animate-eyes 10s infinite linear;
    transition: all 0.3s ease;
  }
}

.eyes.happy {
  display: none;
  color: #fff;
  gap: 0;

  svg { width: 60px; }
}

.container-wrap:hover .eyes .eye { display: none; }
.container-wrap:hover .eyes.happy { display: flex; }

.container-ai-chat {
  position: absolute;
  width: 100%;
  height: 100%;
  padding: 36px 20px 20px;
  opacity: 0;
  pointer-events: none;

  .chat-close-btn {
    position: absolute;
    top: 12px;
    right: 12px;
    z-index: 3;
    width: 36px;
    height: 36px;
    border: none;
    border-radius: 50%;
    background: rgba(0, 0, 0, 0.08);
    color: rgba(0, 0, 0, 0.6);
    font-size: 24px;
    line-height: 1;
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover { background: rgba(0, 0, 0, 0.15); color: rgba(0, 0, 0, 0.9); }
  }
}

.chat {
  display: flex;
  justify-content: space-between;
  flex-direction: column;
  border-radius: 15px;
  width: 100%;
  height: 100%;
  padding: 50px 12px 12px;
  overflow: hidden;
  background-color: #ffffff;
}

.chat-bot {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  transition: all 0.3s ease;
}

.chat-history {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: rgba(0, 0, 0, 0.03);

  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-thumb { background: #dedfe0; border-radius: 5px; }
}

.chat-empty {
  color: #8b8b8b;
  line-height: 1.5;

  p { margin: 0; font-size: 14px; font-weight: 600; }
}

.chat-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.chat-suggestion {
  border: none;
  border-radius: 14px;
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 500;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #ffffff;
  cursor: pointer;
  transition: all 0.2s ease;

  &:disabled { opacity: 0.35; cursor: not-allowed; }
  &:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }
}

.chat-msg {
  max-width: 92%;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.5;
  border-radius: 16px;
  padding: 10px 16px;
  color: #2c2c2c;
  background: #f3f6fd;
  white-space: pre-wrap;
  word-break: break-word;

  &.user {
    margin-left: auto;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: #ffffff;
  }

  &.assistant { margin-right: auto; }

  &.typing {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    width: fit-content;

    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: linear-gradient(135deg, #667eea, #764ba2);
      animation: aiChatDotPulse 1.4s infinite ease-in-out both;

      &:nth-child(2) { animation-delay: 0.16s; }
      &:nth-child(3) { animation-delay: 0.32s; }
    }
  }
}

.chat textarea {
  background-color: transparent;
  border-radius: 12px;
  border: none;
  width: 100%;
  min-height: 80px;
  max-height: 120px;
  color: #4a4a4a;
  font-size: 14px;
  font-weight: 500;
  padding: 8px;
  resize: none;
  outline: none;

  &::placeholder { color: #ccc; }
  &:focus::placeholder { color: #999; }
}

.options {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding: 12px;
}

.btns-add {
  display: flex;
  gap: 8px;

  button {
    display: flex;
    color: rgba(0, 0, 0, 0.1);
    background-color: transparent;
    border: none;
    cursor: pointer;
    transition: all 0.3s ease;

    &:hover { transform: translateY(-4px); color: #8b8b8b; }
  }
}

.btn-submit {
  display: flex;
  padding: 10px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border-radius: 10px;
  cursor: pointer;
  border: none;
  outline: none;
  opacity: 0.7;
  transition: all 0.15s ease;

  i {
    width: 32px;
    height: 32px;
    padding: 4px;
    background: rgba(0, 0, 0, 0.1);
    border-radius: 8px;
    color: #cfcfcf;
  }

  &:hover { opacity: 1; }
  &:disabled { opacity: 0.35; cursor: not-allowed; }
}

@keyframes aiChatDotPulse {
  0%, 80%, 100% { transform: scale(0.4); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

@keyframes rotate-background-balls {
  from { transform: translateX(-50%) translateY(-50%) rotate(360deg); }
  to { transform: translateX(-50%) translateY(-50%) rotate(0); }
}

@keyframes animate-eyes {
  46% { height: 52px; }
  48% { height: 20px; }
  50% { height: 52px; }
  96% { height: 52px; }
  98% { height: 20px; }
  100% { height: 52px; }
}

// 3D hover effects
.area:nth-child(15):hover ~ .container-wrap .card,
.area:nth-child(15):hover ~ .container-wrap .eyes .eye {
  transform: perspective(var(--perspective)) rotateX(-15deg) rotateY(15deg) translateZ(var(--translateY)) scale3d(1, 1, 1);
}
.area:nth-child(14):hover ~ .container-wrap .card,
.area:nth-child(14):hover ~ .container-wrap .eyes .eye {
  transform: perspective(var(--perspective)) rotateX(-15deg) rotateY(7deg) translateZ(var(--translateY)) scale3d(1, 1, 1);
}
.area:nth-child(13):hover ~ .container-wrap .card,
.area:nth-child(13):hover ~ .container-wrap .eyes .eye {
  transform: perspective(var(--perspective)) rotateX(-15deg) rotateY(0) translateZ(var(--translateY)) scale3d(1, 1, 1);
}
.area:nth-child(12):hover ~ .container-wrap .card,
.area:nth-child(12):hover ~ .container-wrap .eyes .eye {
  transform: perspective(var(--perspective)) rotateX(-15deg) rotateY(-7deg) translateZ(var(--translateY)) scale3d(1, 1, 1);
}
.area:nth-child(11):hover ~ .container-wrap .card,
.area:nth-child(11):hover ~ .container-wrap .eyes .eye {
  transform: perspective(var(--perspective)) rotateX(-15deg) rotateY(-15deg) translateZ(var(--translateY)) scale3d(1, 1, 1);
}

@media (max-width: 768px) {
  .ai-chat-floating { left: 8px; bottom: 8px; }
  .container-wrap.open .content-card { width: 320px; height: 420px; }
  .container-wrap:after { width: 6.5rem; height: 6rem; }
  .container-wrap:hover:after { height: 6.5rem; }
  .content-card { width: 6.5rem; height: 6.5rem; }
}
</style>
