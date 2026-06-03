import Logo from "../components/Logo";

export default function DashboardPage({ auth, onLogout }) {
  const user = auth?.user;
  const displayName = user?.display_name || user?.username || "DocPilot 用户";

  return (
    <main className="dashboard-page">
      <header className="dashboard-header">
        <Logo compact />
        <button className="dashboard-logout" type="button" onClick={onLogout}>
          退出登录
        </button>
      </header>

      <section className="dashboard-panel">
        <p className="dashboard-kicker">登录成功</p>
        <h1>欢迎回来，{displayName}</h1>
        <p>认证 token 已保存，后续知识库、问答和报告页面可以在这里继续接入。</p>
      </section>
    </main>
  );
}
