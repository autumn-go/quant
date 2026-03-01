// 认证上下文
import React, { createContext, useContext, useState, useEffect } from 'react';

interface User {
  id: string;
  username: string;
  isAdmin: boolean;
}

interface AuthContextType {
  user: User | null;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// 模拟用户数据库（实际应该存储在 localStorage 或后端）
const DEFAULT_USERS = [
  { id: '1', username: 'admin', password: 'admin123', isAdmin: true },
];

const STORAGE_KEY = 'quant_users';
const CURRENT_USER_KEY = 'quant_current_user';

// 获取用户列表
const getUsers = () => {
  if (typeof window === 'undefined') return DEFAULT_USERS;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
    // 首次使用，初始化默认用户
    localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_USERS));
    return DEFAULT_USERS;
  } catch (e) {
    return DEFAULT_USERS;
  }
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);

  // 页面加载时检查是否已登录
  useEffect(() => {
    const currentUser = localStorage.getItem(CURRENT_USER_KEY);
    if (currentUser) {
      setUser(JSON.parse(currentUser));
    }
  }, []);

  const login = async (username: string, password: string): Promise<boolean> => {
    const users = getUsers();
    const found = users.find(
      (u: any) => u.username === username && u.password === password
    );
    
    if (found) {
      const { password, ...userWithoutPassword } = found;
      setUser(userWithoutPassword);
      localStorage.setItem(CURRENT_USER_KEY, JSON.stringify(userWithoutPassword));
      return true;
    }
    return false;
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem(CURRENT_USER_KEY);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        logout,
        isAuthenticated: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

// 用户管理相关函数
export const userManager = {
  // 获取所有用户（不含密码）
  getAllUsers: () => {
    if (typeof window === 'undefined') return [];
    const users = getUsers();
    return users.map(({ password, ...user }: any) => user);
  },

  // 添加用户（仅管理员）
  addUser: (username: string, password: string, isAdmin: boolean = false) => {
    if (typeof window === 'undefined') return { success: false, error: '不支持的环境' };
    const users = getUsers();
    
    // 检查用户名是否已存在
    if (users.some((u: any) => u.username === username)) {
      return { success: false, error: '用户名已存在' };
    }

    const newUser = {
      id: Date.now().toString(),
      username,
      password,
      isAdmin,
    };

    users.push(newUser);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(users));
    
    const { password: _, ...userWithoutPassword } = newUser;
    return { success: true, user: userWithoutPassword };
  },

  // 删除用户（仅管理员，不能删除自己）
  deleteUser: (userId: string, currentUserId: string) => {
    if (typeof window === 'undefined') return { success: false, error: '不支持的环境' };
    if (userId === currentUserId) {
      return { success: false, error: '不能删除当前登录账户' };
    }

    const users = getUsers();
    const filtered = users.filter((u: any) => u.id !== userId);
    
    if (filtered.length === users.length) {
      return { success: false, error: '用户不存在' };
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
    return { success: true };
  },

  // 修改密码
  changePassword: (userId: string, oldPassword: string, newPassword: string) => {
    if (typeof window === 'undefined') return { success: false, error: '不支持的环境' };
    const users = getUsers();
    const userIndex = users.findIndex((u: any) => u.id === userId);
    
    if (userIndex === -1) {
      return { success: false, error: '用户不存在' };
    }

    if (users[userIndex].password !== oldPassword) {
      return { success: false, error: '原密码错误' };
    }

    users[userIndex].password = newPassword;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(users));
    return { success: true };
  },
};
