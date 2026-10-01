import React, { useState } from 'react';
import { X, Cpu } from 'lucide-react';
import { ModelsResponse } from '../types';

interface ModelCatalogModalProps {
  onClose: () => void;
  selectedModel: string;
  onSelectModel: (m: string) => void;
  modelsData?: ModelsResponse;
}

export const ModelCatalogModal: React.FC<ModelCatalogModalProps> = ({
  onClose,
  selectedModel,
  onSelectModel,
}) => {
  const [filter, setFilter] = useState<'All' | 'Reasoning' | 'Coding' | 'Research' | 'Speed' | 'Writing'>('All');

  const allModels = [
    // Ollama Local Models
    {
      id: 'ollama/qwen2.5-coder:7b',
      name: 'Qwen 2.5 Coder 7B',
      provider: 'Ollama Local',
      category: ['Coding', 'Reasoning', 'Speed'],
      badge: 'Local',
      desc: 'Alibaba’s state-of-the-art local coding model. Offline & private.',
    },
    {
      id: 'ollama/deepseek-coder:6.7b',
      name: 'DeepSeek Coder 6.7B',
      provider: 'Ollama Local',
      category: ['Coding', 'Research'],
      badge: 'Local',
      desc: 'High-precision code completion and refactoring engine.',
    },
    // Cloud Models
    {
      id: 'gemini-2.5-flash',
      name: 'Gemini 2.5 Flash',
      provider: 'Google Gemini',
      category: ['Speed', 'Coding', 'Writing'],
      badge: 'Fast',
      desc: 'Google’s lightning-fast multimodal reasoning model.',
    },
    {
      id: 'gemini-2.5-pro',
      name: 'Gemini 2.5 Pro',
      provider: 'Google Gemini',
      category: ['Reasoning', 'Coding', 'Research'],
      badge: 'Pro',
      desc: 'Deep reasoning, massive 1M context window for full repo analysis.',
    },
    {
      id: 'groq',
      name: 'Llama 3.3 70B (Versatile)',
      provider: 'Groq Cloud',
      category: ['Speed', 'Reasoning', 'Coding'],
      badge: '300 t/s',
      desc: 'Meta Llama 3.3 running at 300 tokens/sec with 14.4k req/day free.',
    },
    {
      id: 'qwen-2.5-coder-32b',
      name: 'Qwen 2.5 Coder 32B',
      provider: 'Groq Cloud',
      category: ['Coding', 'Reasoning'],
      badge: 'Pro',
      desc: 'Full 32B coding heavyweight running at ultra high speed.',
    },
    {
      id: 'teja-gemma',
      name: 'TejaAI Gemma-4 2B (GPU)',
      provider: 'TejaAI Cloud',
      category: ['Coding', 'Speed'],
      badge: 'Fine-Tuned',
      desc: 'Fine-tuned Gemma-4 agent server running on dedicated Colab/Kaggle GPU.',
    },
  ];

  const filtered = allModels.filter((m) => {
    if (filter === 'All') return true;
    return m.category.includes(filter);
  });

  return (
    <div className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs flex items-center justify-center z-50 p-4 select-none">
      <div className="bg-white border border-slate-200 rounded-2xl max-w-3xl w-full p-6 shadow-xl space-y-5 animate-in fade-in zoom-in duration-150">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 pb-4">
          <div>
            <h2 className="text-base font-bold text-slate-900 flex items-center space-x-2">
              <Cpu className="w-5 h-5 text-slate-800" />
              <span>Model Catalog</span>
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">Explore leading AI models, enhanced by ASTRA AI</p>
          </div>
          <button onClick={onClose} className="p-1 rounded-md hover:bg-slate-100 text-slate-500 hover:text-slate-800">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center space-x-2 text-xs">
          {(['All', 'Reasoning', 'Coding', 'Research', 'Speed', 'Writing'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`px-3 py-1.5 rounded-full font-medium transition-colors ${
                filter === tab
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:text-slate-900'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Grid of Models */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[380px] overflow-y-auto pr-1">
          {filtered.map((m) => {
            const isSelected = selectedModel === m.id || (m.id.startsWith('ollama') && selectedModel.includes(m.name.toLowerCase()));
            return (
              <div
                key={m.id}
                onClick={() => {
                  onSelectModel(m.id);
                  onClose();
                }}
                className={`p-3.5 rounded-xl cursor-pointer border transition-all ${
                  isSelected
                    ? 'bg-slate-50 border-slate-900 shadow-xs'
                    : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/50'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center space-x-2">
                    <span className="w-4 h-4 rounded-md bg-slate-900 flex items-center justify-center text-white text-[9px] font-bold">
                      ✦
                    </span>
                    <span className="font-semibold text-slate-900 text-xs">{m.name}</span>
                  </div>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-mono border border-slate-200">
                    {m.badge}
                  </span>
                </div>
                <p className="text-slate-600 text-[11px] line-clamp-2 leading-relaxed">{m.desc}</p>
                <div className="mt-2 text-[10px] text-slate-400 font-mono">{m.provider}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
