function AuthForm({ onAuthenticated, notice }) {
  const [mode, setMode] = React.useState("login");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState("");
  const [success, setSuccess] = React.useState("");
  const registering = mode === "register";

  const submit = async (event) => {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setError("");
    setSuccess("");
    try {
      if (registering) {
        await registerUser(email, password);
        setPassword("");
        setMode("login");
        setSuccess("Conta criada! Entre com seu e-mail e senha.");
      } else {
        const user = await loginUser(email, password);
        setPassword("");
        onAuthenticated(user);
      }
    } catch (err) {
      setError(err.message || "Não foi possível conectar. Tente novamente.");
    } finally {
      setPending(false);
    }
  };

  const switchMode = () => {
    setMode(registering ? "login" : "register");
    setPassword("");
    setError("");
    setSuccess("");
  };

  return (
    <section className="auth-page">
      <div className="auth-card">
        <div className="brand">ChatLLM Lab</div>
        <h1>{registering ? "Crie sua conta" : "Entre para conversar"}</h1>
        <p className="auth-description">
          {registering ? "Cadastre seu e-mail e escolha uma senha." : "Acesse o chat com seu e-mail e senha."}
        </p>
        {notice && <p className="auth-notice" role="status">{notice}</p>}
        {success && <p className="auth-success" role="status">{success}</p>}
        {error && <p className="auth-error" role="alert">{error}</p>}
        <form className="auth-form" onSubmit={submit}>
          <label htmlFor="auth-email">E-mail</label>
          <input
            id="auth-email" name="email" type="email" autoComplete="username"
            value={email} onChange={(event) => setEmail(event.target.value)}
            maxLength={254} required disabled={pending} autoFocus
          />
          <label htmlFor="auth-password">Senha</label>
          <input
            id="auth-password" name="password" type="password"
            autoComplete={registering ? "new-password" : "current-password"}
            value={password} onChange={(event) => setPassword(event.target.value)}
            minLength={registering ? 15 : 1} maxLength={128} required disabled={pending}
            aria-describedby={registering ? "password-help" : undefined}
          />
          {registering && <small id="password-help">Use entre 15 e 128 caracteres. Uma frase longa é uma boa opção.</small>}
          <button className="auth-submit" type="submit" disabled={pending}>
            {pending ? "Aguarde…" : registering ? "Criar conta" : "Entrar"}
          </button>
        </form>
        <button className="auth-switch" type="button" onClick={switchMode} disabled={pending}>
          {registering ? "Já tem conta? Entrar" : "Ainda não tem conta? Cadastre-se"}
        </button>
      </div>
    </section>
  );
}
