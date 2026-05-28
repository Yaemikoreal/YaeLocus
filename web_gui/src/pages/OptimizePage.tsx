export default function OptimizePage() {
  return (
    <div className="page">
      <div className="card">
        <div className="card-title"><i className="fa-solid fa-diagram-project" /> 行程优化</div>
        <p className="card-desc">DBSCAN 聚类分析 + TSP 求解器，智能推荐最优路线</p>
        <div className="empty-state">
          <i className="fa-solid fa-diagram-project" />
          <h4>行程优化功能</h4>
          <p>请先完成地理编码，然后使用 AI 助手的路线分析功能规划行程</p>
          <div style={{ marginTop: 16 }}>
            <a href="/ai" className="btn btn-primary">
              <i className="fa-solid fa-wand-magic-sparkles" /> 前往 AI 助手
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
