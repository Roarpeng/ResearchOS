import { useState } from "react";
import { useEditorStore, useUiStore } from "@paperhelp/shared";
import { Button } from "@paperhelp/ui";
import reactLogo from "./assets/react.svg";
import { invoke } from "@tauri-apps/api/core";
import "./App.css";
import { useThemeEffect } from "./hooks/useThemeEffect";

function App() {
  useThemeEffect();

  const theme = useUiStore((s) => s.theme);
  const setTheme = useUiStore((s) => s.setTheme);
  const title = useEditorStore((s) => s.title);
  const setTitle = useEditorStore((s) => s.setTitle);

  const [greetMsg, setGreetMsg] = useState("");
  const [name, setName] = useState("");

  async function greet() {
    setGreetMsg(await invoke("greet", { name }));
  }

  return (
    <main className="container">
      <h1>Welcome to PaperHelp</h1>
      <p className="subtitle">
        {title.trim() || "Untitled"} · Tauri + React + TypeScript
      </p>

      <div className="row">
        <label htmlFor="doc-title">Document title</label>
        <input
          id="doc-title"
          value={title}
          onChange={(e) => setTitle(e.currentTarget.value)}
          placeholder="Untitled"
        />
      </div>

      <div className="row">
        <label htmlFor="theme-select">Theme</label>
        <select
          id="theme-select"
          value={theme}
          onChange={(e) =>
            setTheme(e.currentTarget.value as "light" | "dark" | "system")
          }
        >
          <option value="light">Light</option>
          <option value="dark">Dark</option>
          <option value="system">System</option>
        </select>
      </div>

      <div className="row">
        <a href="https://vite.dev" target="_blank" rel="noreferrer">
          <img src="/vite.svg" className="logo vite" alt="Vite logo" />
        </a>
        <a href="https://tauri.app" target="_blank" rel="noreferrer">
          <img src="/tauri.svg" className="logo tauri" alt="Tauri logo" />
        </a>
        <a href="https://react.dev" target="_blank" rel="noreferrer">
          <img src={reactLogo} className="logo react" alt="React logo" />
        </a>
      </div>

      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault();
          greet();
        }}
      >
        <input
          id="greet-input"
          onChange={(e) => setName(e.currentTarget.value)}
          placeholder="Enter a name..."
        />
        <Button type="submit">Greet</Button>
      </form>
      <p>{greetMsg}</p>
    </main>
  );
}

export default App;
