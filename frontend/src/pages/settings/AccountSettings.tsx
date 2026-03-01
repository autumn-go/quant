// 账户管理页面（设置子页面）
import React, { useState, useEffect } from 'react';
import { useAuth, userManager } from '../../contexts/AuthContext';
import { 
  Users, 
  Plus, 
  Trash2, 
  Shield, 
  User as UserIcon,
  X,
  Check,
  AlertCircle
} from 'lucide-react';
import './AccountSettings.css';

interface User {
  id: string;
  username: string;
  isAdmin: boolean;
}

const AccountSettings: React.FC = () => {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [isAdmin, setIsAdmin] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // 加载用户列表
  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = () => {
    const allUsers = userManager.getAllUsers();
    setUsers(allUsers);
  };

  // 添加用户
  const handleAddUser = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!newUsername.trim() || !newPassword.trim()) {
      setError('用户名和密码不能为空');
      return;
    }

    if (newPassword.length < 6) {
      setError('密码至少需要6位');
      return;
    }

    const result = userManager.addUser(newUsername.trim(), newPassword, isAdmin);
    
    if (result.success) {
      setSuccess(`用户 ${newUsername} 创建成功`);
      setNewUsername('');
      setNewPassword('');
      setIsAdmin(false);
      setShowAddModal(false);
      loadUsers();
    } else {
      setError(result.error || '创建失败');
    }
  };

  // 删除用户
  const handleDeleteUser = (userId: string, username: string) => {
    if (!currentUser) return;
    
    if (!confirm(`确定要删除用户 "${username}" 吗？此操作不可恢复。`)) {
      return;
    }

    const result = userManager.deleteUser(userId, currentUser.id);
    
    if (result.success) {
      setSuccess(`用户 ${username} 已删除`);
      loadUsers();
    } else {
      setError(result.error || '删除失败');
    }
  };

  // 清空提示
  useEffect(() => {
    if (error || success) {
      const timer = setTimeout(() => {
        setError('');
        setSuccess('');
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [error, success]);

  return (
    <div className="account-settings">
      {/* 页面标题 */}
      <div className="settings-section-header">
        <div className="section-title">
          <Users size={20} />
          <h3>账户管理</h3>
        </div>
        
        {currentUser?.isAdmin && (
          <button 
            className="btn-add-user"
            onClick={() => setShowAddModal(true)}
          >
            <Plus size={18} />
            添加用户
          </button>
        )}
      </div>

      {/* 提示消息 */}
      {error && (
        <div className="alert alert-error">
          <AlertCircle size={18} />
          {error}
        </div>
      )}
      
      {success && (
        <div className="alert alert-success">
          <Check size={18} />
          {success}
        </div>
      )}

      {/* 用户列表 */}
      <div className="users-list">
        <div className="list-header">
          <span>用户</span>
          <span>角色</span>
          <span>操作</span>
        </div>

        {users.map((user) => (
          <div key={user.id} className="user-item">
            <div className="user-info">
              <div className={`user-avatar ${user.isAdmin ? 'admin' : ''}`}>
                {user.isAdmin ? <Shield size={16} /> : <UserIcon size={16} />}
              </div>
              <span className="username">
                {user.username}
                {user.id === currentUser?.id && (
                  <span className="current-badge">当前</span>
                )}
              </span>
            </div>

            <div className="user-role">
              {user.isAdmin ? (
                <span className="role-badge admin">
                  <Shield size={12} />
                  管理员
                </span>
              ) : (
                <span className="role-badge user">
                  <UserIcon size={12} />
                  普通用户
                </span>
              )}
            </div>

            <div className="user-actions">
              {currentUser?.isAdmin && user.id !== currentUser.id && (
                <button
                  className="btn-delete"
                  onClick={() => handleDeleteUser(user.id, user.username)}
                  title="删除用户"
                >
                  <Trash2 size={16} />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 添加用户弹窗 */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h4>添加新用户</h4>
              <button 
                className="btn-close"
                onClick={() => setShowAddModal(false)}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleAddUser}>
              <div className="form-field">
                <label>用户名</label>
                <input
                  type="text"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  placeholder="请输入用户名"
                  autoFocus
                  required
                />
              </div>

              <div className="form-field">
                <label>密码</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="至少6位字符"
                  required
                  minLength={6}
                />
              </div>

              <div className="form-field checkbox">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={isAdmin}
                    onChange={(e) => setIsAdmin(e.target.checked)}
                  />
                  <Shield size={16} />
                  设为管理员
                </label>
              </div>

              <div className="modal-actions">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowAddModal(false)}
                >
                  取消
                </button>
                <button type="submit" className="btn-primary">
                  创建用户
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 说明文字 */}
      <div className="settings-note">
        <p><strong>说明：</strong></p>
        <ul>
          <li>只有管理员可以添加或删除用户</li>
          <li>管理员拥有所有功能的访问权限</li>
          <li>普通用户可以查看数据和执行回测，但不能管理账户</li>
          <li>用户数据存储在浏览器本地，清除浏览器数据会丢失账户信息</li>
        </ul>
      </div>
    </div>
  );
};

export default AccountSettings;
