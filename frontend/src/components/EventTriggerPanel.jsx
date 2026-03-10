import React, { useState } from 'react';
import axios from 'axios';
import { Zap, AlertCircle, CheckCircle2 } from 'lucide-react';

const EventTriggerPanel = ({ modelId, currentState, onTransition }) => {
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);
    const [validTransitions, setValidTransitions] = useState([]);

    // Fetch dynamic valid transitions from backend session
    React.useEffect(() => {
        const fetchState = async () => {
            if (!modelId || !currentState) return;
            try {
                // Fetch recomputed valid transitions for this session
                const res = await axios.get(`/api/model/${modelId}/state?current_state=${currentState.id}`);
                setValidTransitions(res.data.valid_transitions || []);
            } catch (err) {
                console.error("Failed to fetch state validations", err);
            }
        };
        fetchState();
    }, [modelId, currentState]);

    if (!modelId || !currentState) {
        return (
            <div className="bg-white rounded-lg shadow border border-slate-200 p-6 h-full flex flex-col items-center justify-center text-slate-400">
                <Zap className="mb-2 opacity-50" size={32} />
                <p>Load a model to view triggers</p>
            </div>
        );
    }

    const handleTrigger = async (event) => {
        setLoading(true);
        setError(null);
        try {
            const response = await axios.post(`/api/model/${modelId}/transition?current_state=${currentState.id}`, {
                event: event,
                variable_values: {} // Variables are now abstracted away
            });
            onTransition(response.data.new_state);
        } catch (err) {
            if (err.response && err.response.status === 409) {
                setError(err.response.data.detail.message || `Transition '${event}' forbidden by FSM constraints.`);
            } else {
                setError(`API Error: Transition '${event}' failed.`);
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="bg-white rounded-lg shadow border border-slate-200 flex flex-col h-full overflow-hidden">
            <div className="bg-slate-50 border-b border-slate-200 p-4 shrink-0">
                <h2 className="font-semibold text-slate-800 text-sm uppercase tracking-wider mb-1">System Mode</h2>
                <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-pulse shadow-sm shadow-emerald-400"></div>
                    <span className="text-xl font-bold text-slate-800">
                        {currentState.name}
                        <span className="text-slate-400 text-sm font-normal ml-2">({currentState.id})</span>
                    </span>
                </div>
            </div>

            <div className="flex-grow overflow-y-auto p-4 flex flex-col min-h-0">
                <h3 className="font-medium text-slate-700 mb-3 pb-2 border-b shrink-0 flex items-center gap-2">
                    <Zap size={16} className="text-amber-500" />
                    What is happening?
                </h3>

                <div className="space-y-2 flex-grow">
                    {validTransitions.length > 0 ? (
                        validTransitions.map((t, idx) => (
                            <button
                                key={idx}
                                disabled={loading}
                                onClick={() => handleTrigger(t.event)}
                                className="w-full text-left bg-white border border-slate-200 hover:border-amber-400 hover:bg-amber-50 text-slate-700 hover:text-amber-700 font-medium rounded-lg p-3 transition-colors flex items-center justify-between group shadow-sm"
                            >
                                <span className="capitalize">{t.event.replace(/_/g, ' ')}</span>
                                <Zap size={16} className="text-slate-300 group-hover:text-amber-500" />
                            </button>
                        ))
                    ) : (
                        <div className="text-sm text-slate-500 italic p-4 bg-slate-50 rounded-lg border border-slate-100 text-center flex flex-col items-center gap-2">
                            <CheckCircle2 size={24} className="text-emerald-400" />
                            <span>No further actions required.</span>
                            {currentState.is_terminal && <span className="text-xs font-semibold uppercase tracking-wider mt-1">Terminal State</span>}
                        </div>
                    )}
                </div>

                {error && (
                    <div className="mt-4 bg-red-50 text-red-700 p-3 rounded-lg text-sm border border-red-200 flex items-start gap-2 shrink-0 animate-in fade-in slide-in-from-bottom-2">
                        <AlertCircle size={16} className="mt-0.5 shrink-0" />
                        <div>
                            <p className="font-semibold">Event Blocked</p>
                            <p>{error}</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default EventTriggerPanel;
