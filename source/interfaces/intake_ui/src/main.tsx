// See architecture: docs/zoros_architecture.md#ui-blueprint
import React from "react";
import ReactDOM from "react-dom/client";
import { IntakeContainer } from "./intake/IntakeContainer";
import { ZorosStoreProvider } from "./common/hooks/useZorosStore";
import TaskTable from "./components/TaskTable";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ZorosStoreProvider>
      <IntakeContainer />
      <TaskTable />
    </ZorosStoreProvider>
  </React.StrictMode>,
);
