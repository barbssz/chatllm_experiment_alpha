function Sidebar({ sessions, activeId, onSelect, onNew, busy, open }) {
  return (
    <aside className={`sidebar${open ? " sidebar-open" : ""}`} aria-label="Conversas">
      <div className="sidebar-header">
        <span className="sidebar-title">Conversas</span>
      </div>

      <button className="sidebar-new" type="button" onClick={onNew} disabled={busy}>
        + Nova conversa
      </button>

      <nav className="sidebar-list">
        {sessions.length === 0 && (
          <p className="sidebar-empty">Nenhuma conversa ainda.</p>
        )}
        {sessions.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`sidebar-item${item.id === activeId ? " active" : ""}`}
            onClick={() => onSelect(item.id)}
            title={item.title || "Nova conversa"}
            aria-current={item.id === activeId ? "true" : undefined}
          >
            {item.title || "Nova conversa"}
          </button>
        ))}
      </nav>
    </aside>
  );
}
