import React, { useState } from 'react';
import { Send, Bot, AlertCircle } from 'lucide-react';
import axios from 'axios';

const ChatbotPanel = ({ modelId, currentStateId, currentVariables, onTransition }) => {
    const [messages, setMessages] = useState([
        { role: 'system', text: 'Chatbot model constrained assistant. Ask me what to do.' }
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!input.trim() || !modelId || !currentStateId) return;

        const userText = input.trim();
        setMessages(prev => [...prev, { role: 'user', text: userText }]);
        setInput('');
        setLoading(true);

        // Phase 6 actual call
        try {
            const response = await axios.post('/api/chatbot/query', {
                model_id: modelId,
                user_input: userText,
                current_state: currentStateId,
                variable_values: currentVariables
            });

            const data = response.data;
            setMessages(prev => [...prev, { role: 'system', text: data.response_text, confidence: data.confidence }]);

            if (data.transition_taken && data.new_state && onTransition) {
                onTransition(data.new_state);
            }
        } catch (error) {
            setMessages(prev => [...prev, { role: 'error', text: 'Failed to communicate with chatbot API.' }]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="bg-white rounded-lg shadow-md border border-gray-200 flex flex-col h-full overflow-hidden">
            <div className="bg-indigo-50 border-b border-indigo-100 p-3 flex justify-between items-center">
                <h2 className="font-semibold text-indigo-800 text-sm flex items-center gap-2">
                    <Bot size={16} />
                    Formal Assistant
                </h2>
            </div>

            <div className="flex-grow p-4 overflow-y-auto flex flex-col gap-3">
                {messages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[85%] rounded-lg p-3 text-sm ${msg.role === 'user'
                            ? 'bg-blue-600 text-white rounded-br-none'
                            : msg.role === 'error'
                                ? 'bg-red-50 text-red-700 border border-red-200'
                                : 'bg-gray-100 text-gray-800 rounded-bl-none'
                            }`}>
                            {msg.role === 'system' && msg.confidence && (
                                <div className="text-[10px] text-gray-500 mb-1 flex justify-between">
                                    <span>Confidence</span>
                                    <span>{(msg.confidence * 100).toFixed(0)}%</span>
                                </div>
                            )}
                            {msg.text}
                        </div>
                    </div>
                ))}
                {loading && (
                    <div className="flex justify-start">
                        <div className="bg-gray-100 rounded-lg rounded-bl-none p-3 text-sm text-gray-400 flex gap-1 items-center">
                            <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"></div>
                            <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                            <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                        </div>
                    </div>
                )}
            </div>

            <div className="p-3 border-t bg-gray-50">
                <form onSubmit={handleSubmit} className="flex gap-2">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        disabled={!modelId || !currentStateId}
                        placeholder={"What should I do next?"}
                        className="flex-grow border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-200"
                    />
                    <button
                        type="submit"
                        disabled={!modelId || !currentStateId || !input.trim() || loading}
                        className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white p-2 rounded-md transition-colors"
                    >
                        <Send size={18} />
                    </button>
                </form>
            </div>
        </div>
    );
};

export default ChatbotPanel;
