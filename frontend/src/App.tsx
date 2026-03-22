import { Toaster } from "react-hot-toast";
import { useAppStore } from "./store/appStore";
import Sidebar from "./components/Layout/Sidebar";
import Dashboard from "./components/Dashboard/Dashboard";
import TransactionList from "./components/TransactionList/TransactionList";
import ChatInterface from "./components/ChatInterface/ChatInterface";
import BudgetPanel from "./components/BudgetPanel/BudgetPanel";

function App() {
  const { currentView } = useAppStore();

  return (
    <div className="app">
      <Toaster
        position="top-right"
        toastOptions={{
          style: { background: "#1e1e2e", color: "#fff", border: "1px solid #333" },
        }}
      />
      <Sidebar />
      <main className="main-content">
        {currentView === "dashboard" && <Dashboard />}
        {currentView === "transactions" && <TransactionList />}
        {currentView === "chat" && <ChatInterface />}
        {currentView === "budget" && <BudgetPanel />}
      </main>
    </div>
  );
}

export default App;
