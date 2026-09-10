const { useEffect, useMemo, useRef, useState } = React;

function createMessageId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState("");
  const [notice, setNotice] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState("");
  const sessionRequestRef = useRef(0);

  const refreshSession = async () => {
    const requestId = ++sessionRequestRef.current;
    try {
      const currentUser = await getCurrentUser();
      if (requestId !== sessionRequestRef.current) return;
      setUser(currentUser);
      setSessionError("");
    } catch (err) {
      if (requestId !== sessionRequestRef.current) return;
      if (err.status === 401) {
        setUser(null);
        setSessionError("");
      } else {
        setSessionError("Não foi possível verificar sua sessão. Tente novamente.");
      }
    } finally {
      if (requestId === sessionRequestRef.current) setLoading(false);
    }
  };

  useEffect(() => {
    refreshSession();
    // Atualiza a identidade quando o usuario volta de outra aba.
    window.addEventListener("focus", refreshSession);
    return () => {
      sessionRequestRef.current += 1;
      window.removeEventListener("focus", refreshSession);
    };
  }, []);

  const authenticated = (currentUser) => {
    sessionRequestRef.current += 1;
    setUser(currentUser);
    setNotice("");
    setSessionError("");
    setLogoutError("");
  };

  const sessionExpired = () => {
    sessionRequestRef.current += 1;
    setUser(null);
    setNotice("Sua sessão expirou. Entre novamente para continuar.");
  };

  const logout = async () => {
    if (loggingOut) return;
    sessionRequestRef.current += 1;
    setLoggingOut(true);
    setLogoutError("");
    try {
      await logoutUser();
      sessionRequestRef.current += 1;
      setUser(null);
      setNotice("Você saiu da sua conta.");
    } catch (err) {
      setLogoutError("Não foi possível confirmar a saída. Tente novamente.");
    } finally {
      setLoggingOut(false);
    }
  };

  if (loading) return <main className="auth-page" role="status">Verificando sua sessão…</main>;
  if (sessionError) return (
    <main className="auth-page">
      <div className="auth-card">
        <p role="alert">{sessionError}</p>
        <button className="auth-submit" onClick={refreshSession}>Tentar novamente</button>
      </div>
    </main>
  );
  if (!user) return <AuthForm onAuthenticated={authenticated} notice={notice} />;

  // A chave e a desmontagem descartam mensagens e cancelam streams ao trocar de conta.
  return <Chat key={user.id} user={user} onLogout={logout} loggingOut={loggingOut}
    logoutError={logoutError} onSessionExpired={sessionExpired} />;
}

function welcomeMessage() {
  return {
    id: createMessageId(),
    role: "assistant",
    content: "Bem-vindo ao ChatLLM Lab. Como posso ajudar voce hoje?",
  };
}

function Chat({ user, onLogout, loggingOut, logoutError, onSessionExpired }) {
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [starting, setStarting] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sessionError, setSessionError] = useState("");
  const [messages, setMessages] = useState([welcomeMessage()]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const messagesRef = useRef(null);
  const abortControllerRef = useRef(null);
  const loadRef = useRef(0);

  useEffect(() => {
    const el = messagesRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const loadMessages = async (sessionId) => {
    const requestId = ++loadRef.current;
    const items = await getSessionMessages(sessionId);
    if (requestId !== loadRef.current) return;
    setMessages(
      items.length
        ? items.map((item) => ({ id: `server-${item.id}`, role: item.role, content: item.content }))
        : [welcomeMessage()]
    );
  };

  const openSession = async (sessionId) => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    loadRef.current += 1;
    setBusy(false);
    setError("");
    setSessionError("");
    setActiveId(sessionId);
    setSidebarOpen(false);
    try {
      await loadMessages(sessionId);
    } catch (err) {
      if (err.status === 401) {
        onSessionExpired();
        return;
      }
      setSessionError("Não foi possível abrir esta conversa.");
    }
  };

  const startNewConversation = () => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    loadRef.current += 1;
    setBusy(false);
    setError("");
    setSessionError("");
    setActiveId(null);
    setMessages([welcomeMessage()]);
    setSidebarOpen(false);
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await listSessions();
        if (cancelled) return;
        setSessions(list);
        if (list.length > 0) await openSession(list[0].id);
      } catch (err) {
        if (err.status === 401) {
          onSessionExpired();
          return;
        }
        if (!cancelled) setSessionError("Não foi possível carregar suas conversas.");
      } finally {
        if (!cancelled) setStarting(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  const onStop = () => {
    abortControllerRef.current?.abort();
  };

  const onSubmit = async (event, inputRef) => {
    event.preventDefault();
    const cleaned = text.trim();
    if (!cleaned || busy || loggingOut || starting) return;

    setError("");
    setSessionError("");
    const userMessage = { id: createMessageId(), role: "user", content: cleaned };
    const assistantMessageId = createMessageId();

    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: assistantMessageId, role: "assistant", content: "" },
    ]);
    setText("");
    setBusy(true);
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      let sessionId = activeId;
      if (!sessionId) {
        const created = await createSession();
        sessionId = created.id;
        setActiveId(created.id);
        setSessions((prev) => [created, ...prev]);
      }

      await sendMessageStream({
        message: cleaned,
        sessionId,
        signal: abortController.signal,
        onDelta: (delta) => {
          if (abortController.signal.aborted) return;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, content: `${msg.content}${delta}` }
                : msg
            )
          );
        },
        onSession: ({ sessionId: resolvedId, title }) => {
          if (!resolvedId) return;
          setActiveId((current) => current || resolvedId);
          setSessions((prev) => {
            const existing = prev.find((item) => item.id === resolvedId);
            const updated = { ...(existing || { id: resolvedId }), id: resolvedId };
            if (title) updated.title = title;
            return [updated, ...prev.filter((item) => item.id !== resolvedId)];
          });
        },
      });

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId && !msg.content.trim()
            ? { ...msg, content: "Nao foi possivel obter resposta do modelo agora." }
            : msg
        )
      );
    } catch (err) {
      if (err.status === 401) {
        onSessionExpired();
        return;
      }
      const aborted = err?.name === "AbortError";
      if (!aborted) {
        setError(err.message || "Falha inesperada ao gerar resposta.");
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? { ...msg, content: msg.content.trim() ? msg.content : "Nao foi possivel obter resposta do modelo agora." }
              : msg
          )
        );
      } else {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId && !msg.content.trim()
              ? { ...msg, content: "Resposta interrompida." }
              : msg
          )
        );
      }
    } finally {
      if (abortControllerRef.current === abortController) {
        abortControllerRef.current = null;
        setBusy(false);
      }
    }
  };

  return (
    <main className="app-shell">
      <Sidebar
        sessions={sessions}
        activeId={activeId}
        onSelect={openSession}
        onNew={startNewConversation}
        busy={busy}
        open={sidebarOpen}
      />
      {sidebarOpen && (
        <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} aria-hidden="true" />
      )}

      <div className="chat-column">
        <header className="app-header">
          <div className="header-left">
            <button
              className="sidebar-toggle"
              type="button"
              onClick={() => setSidebarOpen((value) => !value)}
              aria-label="Abrir conversas"
            >
              ☰
            </button>
            <div className="brand">ChatLLM Lab</div>
          </div>
          <div className="account-menu">
            <span className="account-email" title={user.email}>{user.email}</span>
            <button className="logout-button" disabled={loggingOut}
              onClick={() => { onStop(); onLogout(); }}>
              {loggingOut ? "Saindo…" : "Sair"}
            </button>
          </div>
        </header>
        {logoutError && <p className="auth-error logout-error" role="alert">{logoutError}</p>}

        <section className="messages" aria-live="polite" ref={messagesRef}>
          <div className="messages-inner">
            {starting && <p className="note" role="status">Carregando suas conversas…</p>}
            {!starting && sessionError && <p className="note error" role="alert">{sessionError}</p>}
            {!starting && messages.map((msg) => (
              <article key={msg.id} className={`bubble ${msg.role}`}>
                <MessageContent content={msg.content} />
              </article>
            ))}
          </div>
        </section>

        <Composer
          text={text}
          busy={busy}
          error={error}
          onChangeText={setText}
          onSubmit={onSubmit}
          onStop={onStop}
        />

        <div className="warning-banner">Lembre-se, você precisa focar no experimento!!!</div>
      </div>
    </main>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);

