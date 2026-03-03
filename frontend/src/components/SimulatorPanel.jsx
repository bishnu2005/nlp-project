import React, { useState } from 'react';
import axios from 'axios';
import { Play, AlertCircle, CheckCircle2 } from 'lucide-react';

const SimulatorPanel = ({ modelData, modelId, currentState, currentVariables, onTransition, onVariableChange }) => {
    const [error, setError] = useState(null);
    const [guardResult, setGuardResult] = useState(null);
    const [loading, setLoading] = useState(false);

    if (!modelData || !currentState) {
        return (
            <div className="bg-white rounded-lg shadow-md border border-gray-200 p-6 h-full flex items-center justify-center text-gray-400">
                Load a model to start simulation
            </div>
        );
    }

    const validTransitions = modelData.transitions.filter(t => t.from_state === currentState.id);

    const handleTransition = async (event) => {
        setLoading(true);
        setError(null);
        setGuardResult(null);

        try {
            const response = await axios.post(`/api/model/${modelId}/transition?current_state=${currentState.id}`, {
                event: event,
                variable_values: currentVariables
            });

            onTransition(response.data.new_state);
            if (response.data.guard_evaluation) {
                setGuardResult(response.data.guard_evaluation);
            }
        } catch (err) {
            if (err.response && err.response.status === 409) {
                setError(err.response.data.detail.message || "Transition forbidden by guard.");
                if (err.response.data.detail.guard_evaluation) {
                    setGuardResult(err.response.data.detail.guard_evaluation);
                }
            } else {
                setError("API Error: Transition failed.");
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="bg-white rounded-lg shadow-md border border-gray-200 flex flex-col h-full overflow-hidden">
            <div className="bg-blue-50 border-b border-blue-100 p-4">
                <h2 className="font-semibold text-blue-800 text-sm uppercase tracking-wider mb-1">Current State</h2>
                <div className="flex items-center gap-2">
                    <div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse shadow-sm shadow-blue-400"></div>
                    <span className="text-xl font-bold text-gray-800">{currentState.name} <span className="text-gray-400 text-sm font-normal">({currentState.id})</span></span>
                </div>
            </div>

            <div className="flex-grow overflow-y-auto p-4 space-y-6">

                {/* Variables Section */}
                {Object.keys(modelData.variables || {}).length > 0 && (
                    <div>
                        <h3 className="font-medium text-gray-700 mb-3 border-b pb-2">Variables Environment</h3>
                        <div className="space-y-3">
                            {Object.entries(modelData.variables).map(([key, def]) => (
                                <div key={key} className="flex flex-col gap-1">
                                    <label className="text-sm font-medium text-gray-600 flex justify-between">
                                        <span>{key}</span>
                                        <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">{def.type}</span>
                                    </label>
                                    {def.type === 'boolean' ? (
                                        <select
                                            className="border rounded p-1.5 bg-gray-50 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                            value={currentVariables[key] ? "true" : "false"}
                                            onChange={(e) => onVariableChange(key, e.target.value === "true")}
                                        >
                                            <option value="true">True</option>
                                            <option value="false">False</option>
                                        </select>
                                    ) : def.type === 'enum' ? (
                                        <select
                                            className="border rounded p-1.5 bg-gray-50 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                            value={currentVariables[key] || ""}
                                            onChange={(e) => onVariableChange(key, e.target.value)}
                                        >
                                            <option value="" disabled>Select...</option>
                                            {(def.enum_values || []).map(v => (
                                                <option key={v} value={v}>{v}</option>
                                            ))}
                                        </select>
                                    ) : (
                                        <input
                                            type={def.type === 'string' ? "text" : "number"}
                                            step={def.type === 'float' ? "0.1" : "1"}
                                            className="border rounded p-1.5 bg-gray-50 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                            value={currentVariables[key] !== undefined ? currentVariables[key] : ''}
                                            onChange={(e) => {
                                                let val = e.target.value;
                                                if (def.type === 'int') val = parseInt(val, 10);
                                                if (def.type === 'float') val = parseFloat(val);
                                                if (isNaN(val) && def.type !== "string") val = 0;
                                                onVariableChange(key, val);
                                            }}
                                        />
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Valid Actions Panel */}
                <div>
                    <h3 className="font-medium text-gray-700 mb-3 border-b pb-2">Available Actions</h3>
                    {validTransitions.length > 0 ? (
                        <div className="space-y-2">
                            {validTransitions.map(t => (
                                <button
                                    key={t.id}
                                    disabled={loading}
                                    onClick={() => handleTransition(t.event)}
                                    className="w-full text-left bg-white border border-gray-300 hover:border-blue-500 hover:bg-blue-50 hover:text-blue-700 rounded p-3 transition-colors flex items-center justify-between group"
                                >
                                    <span className="font-medium font-mono text-sm">{t.event}</span>
                                    <Play size={16} className="text-gray-400 group-hover:text-blue-500" />
                                </button>
                            ))}
                        </div>
                    ) : (
                        <div className="text-sm text-gray-500 italic p-3 bg-gray-50 rounded border border-gray-100 text-center">
                            No outgoing transitions from this state. {currentState.is_terminal && "(Terminal State)"}
                        </div>
                    )}
                </div>

                {/* Status Messages */}
                {error && (
                    <div className="bg-red-50 text-red-700 p-3 rounded-md text-sm border border-red-200 flex items-start gap-2">
                        <AlertCircle size={16} className="mt-0.5 shrink-0" />
                        <div>
                            <p className="font-semibold">Transition Failed</p>
                            <p>{error}</p>
                        </div>
                    </div>
                )}

                {guardResult && !error && (
                    <div className="bg-green-50 text-green-700 p-3 rounded-md text-sm border border-green-200 flex items-start gap-2">
                        <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
                        <div>
                            <p className="font-semibold">Transition Allowed</p>
                            <p>Guards evaluated successfully.</p>
                        </div>
                    </div>
                )}

            </div>
        </div>
    );
};

export default SimulatorPanel;
