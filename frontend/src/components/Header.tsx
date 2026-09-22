import { Bell, Search } from "lucide-react";

export default function Header() {
  return (
    <header className="header">
      <div>
        <h1>UrbanLens AI</h1>
        <p>Urban Property Intelligence Dashboard</p>
      </div>

      <div className="header-actions">
        <div className="search-box">
          <Search size={18} />
          <input placeholder="Search buildings..." />
        </div>

        <button className="notification-btn">
          <Bell size={20} />
        </button>

        <div className="profile">
          <div className="profile-avatar">TS</div>
          <div>
            <strong>Admin</strong>
            <span>Product Lead</span>
          </div>
        </div>
      </div>
    </header>
  );
}