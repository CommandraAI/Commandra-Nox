import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { cn } from '../lib/utils';

interface Message {
  id: number; role: 'user' | 'assistant'; content: string;
  model?: string; effort?: string; planMode?: boolean; createdAt: string;
}

export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[70%] px-3.5 py-2.5 rounded-2xl rounded-tr-sm bg-[#1a1a1a] border border-[#2a2a2a]">
          <p className="text-sm text-[#e8e8e8] leading-relaxed selectable whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3">
      <div className="w-6 h-6 rounded-full bg-[#111] border border-[#2a2a2a] flex items-center justify-center shrink-0 mt-0.5">
        <svg viewBox="0 0 16 16" fill="none" className="w-3 h-3 text-[#e8e8e8]">
          <path d="M11 13L5 8L11 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M7.5 13L1.5 8L7.5 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      <div className="flex-1 min-w-0 selectable">
        <ReactMarkdown
          className="text-sm text-[#ccc] leading-relaxed prose prose-invert prose-sm max-w-none"
          components={{
            code({ node, className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || '');
              const isBlock = match != null;
              if (isBlock) {
                return (
                  <SyntaxHighlighter
                    style={oneDark as any}
                    language={match![1]}
                    PreTag="div"
                    customStyle={{
                      margin: '8px 0',
                      borderRadius: '8px',
                      fontSize: '12px',
                      border: '1px solid #2a2a2a',
                    }}
                  >
                    {String(children).replace(/\n$/, '')}
                  </SyntaxHighlighter>
                );
              }
              return (
                <code
                  className="bg-[#1a1a1a] text-[#e8e8e8] px-1.5 py-0.5 rounded text-[12px] font-mono border border-[#2a2a2a]"
                  {...props}
                >
                  {children}
                </code>
              );
            },
            p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
            ul: ({ children }) => <ul className="list-disc list-inside mb-3 space-y-1">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal list-inside mb-3 space-y-1">{children}</ol>,
            h1: ({ children }) => <h1 className="text-base font-semibold mb-2 text-[#e8e8e8]">{children}</h1>,
            h2: ({ children }) => <h2 className="text-sm font-semibold mb-2 text-[#e8e8e8]">{children}</h2>,
            h3: ({ children }) => <h3 className="text-sm font-semibold mb-1.5 text-[#ddd]">{children}</h3>,
            blockquote: ({ children }) => (
              <blockquote className="border-l-2 border-[#333] pl-3 text-[#777] italic my-2">
                {children}
              </blockquote>
            ),
          }}
        >
          {message.content}
        </ReactMarkdown>
        {message.planMode && (
          <span className="inline-block mt-2 text-[10px] text-[#444] border border-[#222] px-1.5 py-0.5 rounded">
            Plan mode
          </span>
        )}
      </div>
    </div>
  );
}
