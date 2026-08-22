<!--
Copyright 2024-2026 ChatterMate

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0
-->

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createOrganization } from '@/services/organization'
import { resolveLandingRoute } from '@/router/landing'
import type { BusinessHoursDict } from '@/types/organization'

const router = useRouter()
const step = ref(1)
const fullName = ref('')
const email = ref('')
const password = ref('')
const acceptedTerms = ref(false)
const organizationName = ref('')
const domain = ref('')
const timezone = ref(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC')
const confirmed = ref(false)
const loading = ref(false)
const error = ref('')

const businessHours: BusinessHoursDict = {
  monday: { start: '09:00', end: '17:00', enabled: true },
  tuesday: { start: '09:00', end: '17:00', enabled: true },
  wednesday: { start: '09:00', end: '17:00', enabled: true },
  thursday: { start: '09:00', end: '17:00', enabled: true },
  friday: { start: '09:00', end: '17:00', enabled: true },
  saturday: { start: '09:00', end: '17:00', enabled: false },
  sunday: { start: '09:00', end: '17:00', enabled: false },
}

const validEmail = computed(() => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim()))
const strongPassword = computed(() =>
  password.value.length >= 8 &&
  /[a-z]/.test(password.value) &&
  /[A-Z]/.test(password.value) &&
  /\d/.test(password.value) &&
  /[^A-Za-z0-9]/.test(password.value),
)
const personalValid = computed(() =>
  fullName.value.trim().length >= 2 && validEmail.value && strongPassword.value && acceptedTerms.value,
)
const normalizedDomain = computed(() => domain.value.trim().toLowerCase().replace(/^https?:\/\//, '').replace(/\/$/, ''))
const organizationValid = computed(() =>
  organizationName.value.trim().length >= 2 &&
  /^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/.test(normalizedDomain.value) &&
  normalizedDomain.value.includes('.'),
)

const next = () => {
  error.value = ''
  if (step.value === 1 && personalValid.value) step.value = 2
  else if (step.value === 2 && organizationValid.value) step.value = 3
}

const back = () => {
  error.value = ''
  if (step.value > 1) step.value -= 1
}

const submit = async () => {
  if (!confirmed.value || !personalValid.value || !organizationValid.value) return
  loading.value = true
  error.value = ''
  try {
    await createOrganization({
      name: organizationName.value.trim(),
      domain: normalizedDomain.value,
      timezone: timezone.value,
      business_hours: businessHours,
      admin_email: email.value.trim().toLowerCase(),
      admin_name: fullName.value.trim(),
      admin_password: password.value,
      settings: {},
    })
    await router.push(resolveLandingRoute())
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || 'Could not create your workspace'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="form-panel">
      <div class="auth-logo">
        <span class="logo-mark"><i></i><i></i><i></i></span>
        <span class="logo-word">ChatterMate</span>
      </div>

      <h1>Create your account</h1>
      <p class="auth-sub">Create an isolated workspace for your team. No card required.</p>

      <nav class="steps" aria-label="Signup progress">
        <span :class="{ active: step === 1, done: step > 1 }">Personal Info</span>
        <b>·</b>
        <span :class="{ active: step === 2, done: step > 2 }">Organization</span>
        <b>·</b>
        <span :class="{ active: step === 3 }">Verification</span>
      </nav>

      <form class="auth-form" @submit.prevent="step < 3 ? next() : submit()">
        <template v-if="step === 1">
          <label class="field">
            <span>Full Name</span>
            <input v-model="fullName" type="text" autocomplete="name" placeholder="Enter your full name" required />
          </label>
          <label class="field">
            <span>Email</span>
            <input v-model="email" type="email" autocomplete="email" placeholder="Enter your work email" required />
          </label>
          <label class="field">
            <span>Password</span>
            <input v-model="password" type="password" autocomplete="new-password" placeholder="Create a password" required />
            <small v-if="password && !strongPassword">Use 8+ characters with uppercase, lowercase, number and symbol.</small>
          </label>
          <label class="agreement">
            <input v-model="acceptedTerms" type="checkbox" />
            <span>
              I agree to the
              <a href="https://chattermate.chat/terms_and_conditions.html" target="_blank" rel="noopener">Terms of Service</a>
              and
              <a href="https://chattermate.chat/privacy_policy.html" target="_blank" rel="noopener">Privacy Policy</a>
            </span>
          </label>
          <button class="primary" type="submit" :disabled="!personalValid">Continue</button>
        </template>

        <template v-else-if="step === 2">
          <label class="field">
            <span>Organization Name</span>
            <input v-model="organizationName" type="text" autocomplete="organization" placeholder="Acme Support" required />
          </label>
          <label class="field">
            <span>Company Domain</span>
            <input v-model="domain" type="text" inputmode="url" placeholder="acme.com" required />
            <small>This uniquely identifies and isolates your workspace.</small>
          </label>
          <label class="field">
            <span>Timezone</span>
            <input v-model="timezone" type="text" autocomplete="off" placeholder="Asia/Colombo" required />
          </label>
          <div class="actions">
            <button class="secondary" type="button" @click="back">Back</button>
            <button class="primary" type="submit" :disabled="!organizationValid">Continue</button>
          </div>
        </template>

        <template v-else>
          <div class="review-card">
            <p><span>Workspace</span><strong>{{ organizationName }}</strong></p>
            <p><span>Domain</span><strong>{{ normalizedDomain }}</strong></p>
            <p><span>Owner</span><strong>{{ fullName }}</strong></p>
            <p><span>Login email</span><strong>{{ email }}</strong></p>
          </div>
          <p class="isolation-note">Your users, agents, conversations, knowledge, integrations and settings will be isolated under this organization.</p>
          <label class="agreement">
            <input v-model="confirmed" type="checkbox" />
            <span>I confirm these workspace details are correct.</span>
          </label>
          <div v-if="error" class="auth-error" role="alert">{{ error }}</div>
          <div class="actions">
            <button class="secondary" type="button" :disabled="loading" @click="back">Back</button>
            <button class="primary" type="submit" :disabled="!confirmed || loading">
              {{ loading ? 'Creating workspace…' : 'Create Workspace' }}
            </button>
          </div>
        </template>

        <p class="login-prompt">Already have an account? <RouterLink to="/login">Log in</RouterLink></p>
      </form>
    </section>

    <aside class="brand-panel" aria-label="ChatterMate benefits">
      <div class="blob blob-lime"></div><div class="blob blob-purple"></div><div class="blob blob-teal"></div>
      <div class="brand-copy">
        <div class="orb"><i class="orb-glow"></i><i class="orb-gradient"></i><i class="orb-core"></i></div>
        <div class="badge"><i></i> open source · MCP-native</div>
        <h2>Support that <em>learns itself.</em></h2>
        <p>Reads your knowledge base, answers in any chat design, hands off to humans, and even answers other AI agents over open MCP.</p>
        <ul>
          <li><b>✓</b> Auto-learning knowledge base — drop a PDF or URL</li>
          <li><b>✓</b> Human handoff with full context</li>
          <li><b>✓</b> Tenant-isolated workspaces for every team</li>
        </ul>
      </div>
    </aside>
  </main>
</template>

<style scoped>
.auth-page{min-height:100vh;display:grid;grid-template-columns:1.02fr .98fr;background:var(--bg);color:var(--text);font-family:var(--font-sans)}
.form-panel{display:flex;flex-direction:column;justify-content:center;padding:44px 56px;background:var(--bg);min-height:100dvh}
.auth-logo{display:flex;align-items:center;gap:10px;margin-bottom:30px}.logo-mark{width:32px;height:32px;background:var(--accent-solid);border-radius:10px 10px 10px 2px;display:flex;align-items:center;justify-content:center;gap:3.5px}.logo-mark i{width:4.5px;height:4.5px;background:var(--on-accent);border-radius:50%}.logo-word{font-family:var(--font-display);font-weight:700;font-size:18px}
h1{font-family:var(--font-display);font-size:36px;font-weight:700;letter-spacing:-.03em;line-height:1.1;margin:0 0 10px}.auth-sub{color:var(--muted);font-size:14px;margin:0 0 26px}
.steps{display:grid;grid-template-columns:auto 18px auto 18px auto;align-items:center;max-width:430px;margin-bottom:26px;border-bottom:1px solid var(--o08)}.steps span{padding:10px 0 12px;color:var(--muted2);font-size:12px;text-align:center;border-bottom:2px solid transparent;margin-bottom:-1px}.steps b{color:var(--faint);text-align:center}.steps .active{color:var(--accent-ink);border-color:var(--accent-solid);font-weight:600}.steps .done{color:var(--text3)}
.auth-form{display:flex;flex-direction:column;gap:17px;max-width:430px}.field{display:flex;flex-direction:column;gap:8px}.field>span{font-size:13px;font-weight:500;color:var(--text3)}.field input{width:100%;padding:13px 15px;background:var(--o04);border:1px solid var(--o12);border-radius:11px;color:var(--text);font:14px var(--font-sans);box-sizing:border-box;transition:.18s}.field input::placeholder{color:var(--faint)}.field input:focus{outline:none;border-color:var(--accent-ink);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent-ink) 15%,transparent)}.field small,.isolation-note{font-size:12px;line-height:1.45;color:var(--muted2)}
.agreement{display:flex;align-items:flex-start;gap:9px;color:var(--muted2);font-size:12px;line-height:1.45;cursor:pointer}.agreement input{width:16px;height:16px;margin:1px 0 0;accent-color:var(--accent-solid)}
.agreement a{color:var(--accent-ink);text-decoration:none}.agreement a:hover{text-decoration:underline}
.primary,.secondary{padding:14px;border-radius:11px;font:600 14px var(--font-sans);cursor:pointer;transition:.18s}.primary{flex:1;background:var(--accent-solid);color:var(--on-accent-solid);border:0}.secondary{min-width:92px;color:var(--text3);background:var(--o05);border:1px solid var(--o12)}.primary:hover:not(:disabled),.secondary:hover:not(:disabled){opacity:.86}.primary:disabled,.secondary:disabled{opacity:.42;cursor:not-allowed}.actions{display:flex;gap:10px}
.login-prompt{text-align:center;color:var(--muted2);font-size:13px;margin:1px 0 0}.login-prompt a{color:var(--accent-ink);text-decoration:none;font-weight:500}.login-prompt a:hover{text-decoration:underline}
.review-card{padding:4px 16px;background:var(--o03);border:1px solid var(--o10);border-radius:13px}.review-card p{display:flex;justify-content:space-between;gap:20px;margin:0;padding:12px 0;border-bottom:1px solid var(--o08);font-size:13px}.review-card p:last-child{border:0}.review-card span{color:var(--muted2)}.review-card strong{color:var(--text3);font-weight:500;text-align:right;overflow-wrap:anywhere}.isolation-note{margin:0;padding:11px 13px;border-left:2px solid var(--accent-solid);background:color-mix(in srgb,var(--accent-solid) 5%,transparent)}.auth-error{color:var(--c-coral);background:color-mix(in srgb,var(--c-coral) 10%,transparent);border:1px solid color-mix(in srgb,var(--c-coral) 20%,transparent);border-radius:10px;padding:10px 14px;font-size:13px}
.brand-panel{position:relative;background:linear-gradient(160deg,var(--bg-elevated),var(--bg-deep));overflow:hidden;display:flex;align-items:center;padding:56px 5vw;min-height:100vh;box-sizing:border-box;border-left:1px solid var(--o06)}.blob{position:absolute;border-radius:50%;filter:blur(80px);animation:aurora 14s ease-in-out infinite}.blob-lime{width:420px;height:420px;background:radial-gradient(circle,color-mix(in srgb,var(--accent-solid) 32%,transparent),transparent 70%);top:-80px;right:-60px}.blob-purple{width:360px;height:360px;background:radial-gradient(circle,color-mix(in srgb,var(--c-purple) 28%,transparent),transparent 70%);top:20%;left:-80px;animation-delay:-5s}.blob-teal{width:300px;height:300px;background:radial-gradient(circle,color-mix(in srgb,var(--c-teal) 22%,transparent),transparent 70%);bottom:15%;right:10%;animation-delay:-9s}.brand-copy{position:relative;z-index:1;max-width:460px}.orb{position:relative;width:112px;height:112px;margin-bottom:34px;animation:float 7s ease-in-out infinite}.orb i{position:absolute;border-radius:50%}.orb-glow{inset:-34px;background:radial-gradient(circle,color-mix(in srgb,var(--accent-solid) 20%,transparent),transparent 70%);filter:blur(10px)}.orb-gradient{inset:0;background:conic-gradient(var(--accent-solid),var(--c-purple),var(--c-teal),var(--c-coral),var(--accent-solid));filter:blur(6px);animation:spin 6s linear infinite}.orb-core{inset:23px;background:radial-gradient(circle at 40% 35%,color-mix(in srgb,var(--text) 92%,transparent),color-mix(in srgb,var(--text) 12%,transparent) 55%,transparent 72%)}.badge{display:inline-flex;align-items:center;gap:9px;padding:7px 14px;border:1px solid var(--o12);border-radius:999px;background:var(--o03);font:12px var(--font-mono);color:var(--text3);margin-bottom:26px}.badge i{width:7px;height:7px;border-radius:50%;background:var(--accent-solid);box-shadow:0 0 10px var(--accent-ink)}.brand-copy h2{font-family:var(--font-display);font-size:42px;letter-spacing:-.03em;line-height:1.06;margin:0 0 18px}.brand-copy h2 em{font-style:normal;color:var(--accent-ink)}.brand-copy>p{font-size:17px;line-height:1.6;color:var(--muted);margin:0 0 30px}.brand-copy ul{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:14px}.brand-copy li{display:flex;gap:12px;font-size:15px;color:var(--text3)}.brand-copy li b{color:var(--accent-ink)}
@keyframes spin{to{transform:rotate(360deg)}}@keyframes float{50%{transform:translateY(-10px)}}@keyframes aurora{50%{transform:translate(18px,12px) scale(1.05)}}
@media(max-width:1024px){.auth-page{grid-template-columns:1fr}.brand-panel{display:none}.form-panel{align-items:center}.form-panel>*{width:100%;max-width:430px}}
@media(max-width:600px){.form-panel{padding:34px 24px;justify-content:flex-start}.auth-logo{margin-bottom:28px}h1{font-size:30px}.steps{grid-template-columns:1fr 12px 1fr 12px 1fr}.steps span{font-size:11px}.review-card p{flex-direction:column;gap:4px}.review-card strong{text-align:left}}
</style>
