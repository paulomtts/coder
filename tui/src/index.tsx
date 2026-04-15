import { render } from "ink";
import React from "react";

import { App } from "./App";
import { createInkRenderOptions } from "./terminal";

render(<App />, createInkRenderOptions());
