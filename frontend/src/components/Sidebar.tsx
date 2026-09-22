import {
  LayoutDashboard,
  Map,
  BarChart3,
  FileSearch,
  AlertTriangle,
  ClipboardCheck,
} from "lucide-react";

const menuItems = [
  { name: "Dashboard", icon: LayoutDashboard },
  { name: "Map View", icon: Map },
  { name: "Analytics", icon: BarChart3 },
  { name: "Evidence", icon: FileSearch },
  { name: "Discrepancies", icon: AlertTriangle },
  { name: "Review Queue", icon: ClipboardCheck },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="logo">
        <div className="logo-icon">U</div>
        <div>
          <h2>UrbanLens</h2>
          <span>AI Dashboard</span>
        </div>
      </div>

      <nav>
        {menuItems.map((item, index) => {
          const Icon = item.icon;

          return (
            <div
              key={item.name}
              className={`nav-item ${index === 0 ? "active" : ""}`}
            >
              <Icon size={19} />
              <span>{item.name}</span>
            </div>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <span className="status-dot"></span>
        <div>
          <strong>System Online</strong>
          <small>AI services active</small>
        </div>
      </div>
    </aside>
  );
}