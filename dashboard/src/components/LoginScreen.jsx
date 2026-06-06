import React, { useState } from 'react'

export default function LoginScreen({ onLogin, error, status, connecting }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    onLogin(username.trim(), password)
  }

  const busy = connecting || status === 'connecting'

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={handleSubmit}>
        <div className="login-brand">MINA v2</div>
        <p className="login-subtitle">Dashboard girişi</p>

        <label className="login-label">
          Kullanıcı adı
          <input
            type="text"
            className="login-input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoFocus
            disabled={busy}
          />
        </label>

        <label className="login-label">
          Şifre
          <input
            type="password"
            className="login-input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            disabled={busy}
          />
        </label>

        {error && <div className="login-error" role="alert">{error}</div>}

        <button type="submit" className="login-submit" disabled={busy || !username.trim() || !password}>
          {busy ? 'Bağlanıyor…' : 'Giriş yap'}
        </button>

        <div className="login-status">
          {status === 'connected' && 'Sunucuya bağlı'}
          {status === 'connecting' && 'Bağlanıyor…'}
          {status === 'disconnected' && 'Bağlantı kesildi — yeniden deneniyor'}
          {status === 'error' && 'Bağlantı hatası'}
        </div>
      </form>
    </div>
  )
}
