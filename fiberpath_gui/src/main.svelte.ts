import { mount } from "svelte";
import App from "./App.svelte";
import "./styles/index.css";

const target = document.getElementById("svelte-root");
if (!target) {
  throw new Error("#svelte-root not found");
}

mount(App, { target });
