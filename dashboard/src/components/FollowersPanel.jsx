import React from 'react'

function SideBadge({ side }) {
  const isLong = side === 'LONG'
  return (
    <span className={`side-badge ${isLong ? 'side-badge-long' : 'side-badge-short'}`}>
      {isLong ? 'L' : 'S'}
    </span>
  )
}

function FollowerCard({ follower }) {
  const positions = follower.positions ?? []
  const floating = follower.floatingPnl ?? 0
  const balance = follower.balance ?? 0

  return (
    <div className="follower-card">
      <div className="follower-card-head">
        <div>
          <strong className="follower-name">{follower.name}</strong>
          <span className="follower-meta">{positions.length} pozisyon</span>
        </div>
        <div className="follower-balances">
          <span>Kasa: {Number(balance).toFixed(2)} USDT</span>
          <span className={floating >= 0 ? 'text-green' : 'text-red'}>
            Float: {floating >= 0 ? '+' : ''}{Number(floating).toFixed(2)} USDT
          </span>
        </div>
      </div>
      {positions.length === 0 ? (
        <p className="follower-empty">Açık pozisyon yok</p>
      ) : (
        <div className="follower-pos-list">
          {positions.map((p) => (
            <div key={`${p.symbol}-${p.side}`} className="follower-pos-row">
              <SideBadge side={p.side} />
              <span className="follower-pos-sym">{p.symbol}</span>
              <span>{p.leverage}x</span>
              <span className={p.pnlUSDT >= 0 ? 'text-green' : 'text-red'}>
                {p.pnlUSDT >= 0 ? '+' : ''}{Number(p.pnlUSDT).toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function FollowersPanel({ data, embedded = false }) {
  const followers = data?.followers ?? []

  const body = followers.length === 0 ? (
    <p className="follower-empty">
      Takipçi hesabı yapılandırılmamış.
      .env dosyasına FOLLOWER_1_API_KEY, FOLLOWER_1_SECRET, FOLLOWER_1_NAME ekleyin.
    </p>
  ) : (
    followers.map((f) => <FollowerCard key={f.id} follower={f} />)
  )

  if (embedded) {
    return <div className="followers-embedded">{body}</div>
  }

  return (
    <div className="panel followers-panel">
      <div className="panel-head">
        <span className="panel-title">Takipçiler</span>
        <span className="panel-badge">{followers.length} hesap</span>
      </div>
      <div className="panel-body">{body}</div>
    </div>
  )
}
