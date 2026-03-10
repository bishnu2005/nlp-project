import { useState, useRef } from 'react'
import axios from 'axios'
import GraphPanel from './components/GraphPanel'
import EventTriggerPanel from './components/EventTriggerPanel'
import SourcePanel from './components/SourcePanel'
import ChatbotPanel from './components/ChatbotPanel'
import CompileModal from './components/CompileModal'
import { Upload, Cpu, PenTool } from 'lucide-react'
import './App.css'

function App() {
    const [modelData, setModelData] = useState(null)
    const [modelId, setModelId] = useState(null)
    const [currentStateId, setCurrentStateId] = useState(null)
    const [sourceSentences, setSourceSentences] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [isCompileModalOpen, setIsCompileModalOpen] = useState(false)
    const fileInputRef = useRef(null)

    const handleFileUpload = async (event) => {
        const file = event.target.files[0]
        if (!file) return

        setLoading(true)
        setError(null)

        try {
            const text = await file.text()
            const ibrData = JSON.parse(text)
            await loadIbrIntoSimulator(ibrData)
        } catch (err) {
            setError(err.response?.data?.detail || err.message || 'Failed to load model File')
        } finally {
            setLoading(false)
            if (fileInputRef.current) fileInputRef.current.value = ''
        }
    }

    const loadIbrIntoSimulator = async (ibrData) => {
        const response = await axios.post('/api/model/load', ibrData)

        setModelData(ibrData)
        setModelId(response.data.model_id)
        setCurrentStateId(response.data.initial_state)

        // Load source sentences for initial state
        fetchSourceSentences(response.data.model_id, response.data.initial_state)
    }

    const handleCompileSuccess = async (ibrData, verificationData) => {
        try {
            await loadIbrIntoSimulator(ibrData)
            // Could optionally show verification data via toast here
            console.log("Compilation verification results:", verificationData)
        } catch (err) {
            setError(err.response?.data?.detail || err.message || 'Failed to load compiled model API')
        }
    }

    const fetchSourceSentences = async (mid, sid) => {
        try {
            const response = await axios.get(`/api/model/${mid}/traceability/${sid}`)
            setSourceSentences(response.data.source_sentences)
        } catch (err) {
            console.error("Failed to fetch traceability", err)
            setSourceSentences([])
        }
    }

    const handleStateSelect = (stateId) => {
        // We update source panel but we DONT transition the actual simulator state
        // just by clicking. Click is inspect only.
        if (modelId) fetchSourceSentences(modelId, stateId)
    }

    const handleTransition = (newStateId) => {
        setCurrentStateId(newStateId)
        if (modelId) fetchSourceSentences(modelId, newStateId)
    }

    // Find the full state object for the simulator panel
    const currentStateObj = modelData?.states?.find(s => s.id === currentStateId)

    return (
        <div className="min-h-screen bg-slate-100 flex flex-col font-sans">
            <header className="bg-slate-800 text-white p-4 shadow-md flex justify-between items-center z-10 relative">
                <div className="flex items-center gap-3">
                    <div className="bg-blue-600 p-2 rounded-lg">
                        <Cpu size={24} />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold tracking-tight">Manual-to-UML Simulator</h1>
                        <p className="text-xs text-slate-400">Neuro-Symbolic Compilation Framework</p>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    <button
                        onClick={() => setIsCompileModalOpen(true)}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-md font-medium text-sm transition-colors flex items-center gap-2 shadow-sm border border-indigo-700"
                    >
                        <PenTool size={16} /> Compile Manual
                    </button>
                    <div className="w-px h-6 bg-slate-600 mx-1"></div>
                    <input
                        type="file"
                        accept=".json"
                        className="hidden"
                        ref={fileInputRef}
                        onChange={handleFileUpload}
                    />
                    <button
                        onClick={() => fileInputRef.current?.click()}
                        className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-md font-medium text-sm transition-colors flex items-center gap-2 shadow-sm border border-slate-600"
                    >
                        <Upload size={16} /> Load IBR Model
                    </button>
                </div>
            </header>

            {error && (
                <div className="bg-red-500 text-white p-3 text-sm text-center font-medium shadow-sm">
                    Error: {typeof error === 'string' ? error : JSON.stringify(error)}
                    <button onClick={() => setError(null)} className="ml-4 underline hover:text-red-200">Dismiss</button>
                </div>
            )}

            <main
                className="flex-grow p-4 grid gap-4 overflow-hidden"
                style={{
                    height: 'calc(100vh - 76px)',
                    gridTemplateColumns: '1fr 380px',
                    gridTemplateRows: '100%'
                }}
            >
                {/* Left Column: Graph */}
                <div className="h-full min-h-0 bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                    <GraphPanel
                        modelData={modelData}
                        currentStateId={currentStateId}
                        onStateSelect={handleStateSelect}
                    />
                </div>

                {/* Right Column: Split Top/Middle/Bottom */}
                <div className="flex flex-col gap-4 h-full min-h-0">
                    <div style={{ height: '45%' }} className="min-h-0">
                        <EventTriggerPanel
                            modelId={modelId}
                            currentState={currentStateObj}
                            onTransition={handleTransition}
                        />
                    </div>

                    <div style={{ height: '25%' }} className="min-h-0">
                        <SourcePanel
                            sourceSentences={sourceSentences}
                            selectedStateId={currentStateId}
                        />
                    </div>

                    <div style={{ height: '30%' }} className="min-h-0">
                        <ChatbotPanel
                            modelId={modelId}
                            currentStateId={currentStateId}
                            currentVariables={{}} // Abstracted away
                            onTransition={handleTransition}
                        />
                    </div>
                </div>
            </main>

            <CompileModal
                isOpen={isCompileModalOpen}
                onClose={() => setIsCompileModalOpen(false)}
                onCompileSuccess={handleCompileSuccess}
            />
        </div>
    )
}

export default App
