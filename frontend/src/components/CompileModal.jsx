import React, { useState, useRef } from 'react';
import axios from 'axios';
import { Upload, X, FileText, Image, FileOutput, Loader2 } from 'lucide-react';

const CompileModal = ({ isOpen, onClose, onCompileSuccess }) => {
    const [activeTab, setActiveTab] = useState('text');
    const [manualText, setManualText] = useState('');
    const [selectedFile, setSelectedFile] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const fileInputRef = useRef(null);

    if (!isOpen) return null;

    const handleFileSelect = (e) => {
        const file = e.target.files[0];
        if (file) {
            setSelectedFile(file);
        }
    };

    const handleSubmit = async () => {
        setLoading(true);
        setError(null);

        const formData = new FormData();

        if (activeTab === 'text') {
            if (!manualText.trim()) {
                setError('Please provide some manual text to compile.');
                setLoading(false);
                return;
            }
            formData.append('manual_text', manualText);
        } else {
            if (!selectedFile) {
                setError('Please select a file to upload.');
                setLoading(false);
                return;
            }
            formData.append('file', selectedFile);
        }

        try {
            const response = await axios.post('/api/compile-manual', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            });

            // Compilation success! Pass the IBR model up to App.jsx to be loaded
            onCompileSuccess(response.data.ibr_model, response.data.verification);

            // Reset state
            setManualText('');
            setSelectedFile(null);
            onClose();

        } catch (err) {
            console.error("Compilation error:", err);
            setError(err.response?.data?.detail || err.message || 'An error occurred during compilation.');
        } finally {
            setLoading(false);
        }
    };

    const tabs = [
        { id: 'text', label: 'Paste Text', icon: <FileText size={16} /> },
        { id: 'pdf', label: 'Upload PDF', icon: <FileOutput size={16} /> },
        { id: 'image', label: 'Upload Image', icon: <Image size={16} /> }
    ];

    return (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="flex justify-between items-center p-4 border-b">
                    <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                        <Upload size={20} className="text-blue-600" />
                        Compile New Manual
                    </h2>
                    <button
                        onClick={onClose}
                        className="text-slate-400 hover:text-slate-600 transition-colors"
                        disabled={loading}
                    >
                        <X size={24} />
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex border-b bg-slate-50">
                    {tabs.map(tab => (
                        <button
                            key={tab.id}
                            onClick={() => {
                                setActiveTab(tab.id);
                                setError(null);
                            }}
                            className={`flex flex-1 items-center justify-center gap-2 py-3 px-4 text-sm font-medium transition-colors border-b-2 ${activeTab === tab.id
                                    ? 'border-blue-600 text-blue-600 bg-white'
                                    : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-100'
                                }`}
                        >
                            {tab.icon} {tab.label}
                        </button>
                    ))}
                </div>

                {/* Body */}
                <div className="p-6 flex-grow overflow-y-auto">
                    {error && (
                        <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded-lg flex items-start gap-2 border border-red-200">
                            <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
                            <div>{typeof error === 'string' ? error : JSON.stringify(error)}</div>
                        </div>
                    )}

                    {activeTab === 'text' && (
                        <div className="flex flex-col h-full min-h-[250px]">
                            <label className="block text-sm font-medium text-slate-700 mb-2">
                                Procedural Text Input
                            </label>
                            <textarea
                                value={manualText}
                                onChange={(e) => setManualText(e.target.value)}
                                placeholder="Paste your operational procedures, safety guidelines, or system instructions here..."
                                className="w-full flex-grow p-4 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm resize-none font-mono"
                                disabled={loading}
                            />
                        </div>
                    )}

                    {(activeTab === 'pdf' || activeTab === 'image') && (
                        <div className="flex flex-col items-center justify-center border-2 border-dashed border-slate-300 rounded-xl p-10 bg-slate-50">

                            <input
                                type="file"
                                accept={activeTab === 'pdf' ? '.pdf' : '.jpg,.jpeg,.png'}
                                className="hidden"
                                ref={fileInputRef}
                                onChange={handleFileSelect}
                            />

                            <div className="bg-blue-100 text-blue-600 p-4 rounded-full mb-4">
                                {activeTab === 'pdf' ? <FileOutput size={32} /> : <Image size={32} />}
                            </div>

                            <p className="text-slate-700 font-medium text-lg mb-1">
                                {selectedFile ? selectedFile.name : `Drop your ${activeTab.toUpperCase()} file here`}
                            </p>

                            <p className="text-slate-500 text-sm mb-6 text-center">
                                {selectedFile
                                    ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB`
                                    : `or click to browse your computer`}
                            </p>

                            <button
                                onClick={() => fileInputRef.current?.click()}
                                className="px-4 py-2 bg-white border border-slate-300 rounded-lg text-sm font-medium shadow-sm hover:bg-slate-50 transition-colors"
                                disabled={loading}
                            >
                                Browse Files
                            </button>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-4 border-t bg-slate-50 flex justify-end gap-3 rounded-b-xl">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors"
                        disabled={loading}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSubmit}
                        disabled={loading || (activeTab === 'text' && !manualText.trim()) || (activeTab !== 'text' && !selectedFile)}
                        className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg text-sm font-medium shadow-sm transition-colors flex items-center gap-2"
                    >
                        {loading ? (
                            <>
                                <Loader2 size={16} className="animate-spin" />
                                Compiling via AI...
                            </>
                        ) : (
                            <>
                                <Upload size={16} />
                                Compile to FSM
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};

// Quick polyfill for missing AlertCircle used above
const AlertCircle = ({ size, className }) => (
    <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
    </svg>
);

export default CompileModal;
