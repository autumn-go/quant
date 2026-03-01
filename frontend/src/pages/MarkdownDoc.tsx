import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { ArrowLeft, BookOpen, Loader2 } from 'lucide-react';
import './MarkdownDoc.css';

const MarkdownDoc: React.FC = () => {
  const { filename } = useParams<{ filename: string }>();
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState<string>('算法说明');

  useEffect(() => {
    fetchMarkdown();
  }, [filename]);

  const fetchMarkdown = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const mdFile = filename ? `/${filename}.md` : '/sector_rotation_algorithm.md';
      const response = await fetch(mdFile);
      
      if (!response.ok) {
        throw new Error(`Failed to load: ${response.status}`);
      }
      
      const text = await response.text();
      setContent(text);
      
      // Extract title from first line
      const firstLine = text.split('\n')[0];
      if (firstLine.startsWith('# ')) {
        setTitle(firstLine.replace('# ', ''));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load document');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="markdown-doc loading">
        <Loader2 size={32} className="spin" />
        <p>加载中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="markdown-doc error">
        <p>加载失败: {error}</p>
        <Link to="/sector-rotation" className="back-link">
          <ArrowLeft size={18} /> 返回板块轮动
        </Link>
      </div>
    );
  }

  return (
    <div className="markdown-doc">
      <header className="doc-header">
        <Link to="/sector-rotation" className="back-link">
          <ArrowLeft size={18} />
          <span>返回</span>
        </Link>
        <div className="doc-title">
          <BookOpen size={20} />
          <span>{title}</span>
        </div>
        <div className="doc-spacer"></div>
      </header>
      
      <article className="doc-content">
        <ReactMarkdown 
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[rehypeKatex]}
        >
          {content}
        </ReactMarkdown>
      </article>
    </div>
  );
};

export default MarkdownDoc;
