'use client';

import { useState, useCallback } from 'react';
import FileUpload from '@/components/FileUpload';
import Spinner from '@/components/Spinner';
import { checkHealth, fillQuestionnaire, FillResponse, HealthResponse } from '@/lib/api';
import { downloadCSV } from '@/lib/download';

type AppState = 'idle' | 'processing' | 'ready' | 'error';

export default function Home() {
  const [state, setState] = useState<AppState>('idle');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [result, setResult] = useState<FillResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [healthStatus, setHealthStatus] = useState<HealthResponse | null>(null);
  const [showHealth, setShowHealth] = useState(false);

  const handleFileSelect = useCallback((file: File) => {
    setSelectedFile(file);
    setError(null);
  }, []);

  const handleAutofill = useCallback(async () => {
    if (!selectedFile) return;

    setState('processing');
    setError(null);
    setResult(null);

    try {
      const response = await fillQuestionnaire(selectedFile);
      setResult(response);
      setState('ready');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred');
      setState('error');
    }
  }, [selectedFile]);

  const handleDownload = useCallback(() => {
    if (!result || !selectedFile) return;
    downloadCSV(result.csv_output, selectedFile.name);
  }, [result, selectedFile]);

  const handleReset = useCallback(() => {
    setState('idle');
    setSelectedFile(null);
    setResult(null);
    setError(null);
  }, []);

  const handleCheckHealth = useCallback(async () => {
    try {
      const health = await checkHealth();
      setHealthStatus(health);
      setShowHealth(true);
    } catch (err) {
      setHealthStatus(null);
      setShowHealth(true);
    }
  }, []);

  return (
    <main className="min-h-screen py-12 px-4">
      <div className="max-w-xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Questionnaire Autofill
          </h1>
          <p className="text-gray-600">
            Upload a questionnaire CSV and automatically fill it with answers from the knowledge base
          </p>
        </div>

        {/* Main Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          {/* Idle State */}
          {state === 'idle' && (
            <div className="space-y-6">
              <FileUpload
                onFileSelect={handleFileSelect}
                disabled={false}
              />

              <button
                onClick={handleAutofill}
                disabled={!selectedFile}
                className={`
                  w-full py-3 px-4 rounded-lg font-medium text-white transition-colors
                  ${selectedFile
                    ? 'bg-blue-600 hover:bg-blue-700 cursor-pointer'
                    : 'bg-gray-300 cursor-not-allowed'}
                `}
              >
                Autofill Questionnaire
              </button>
            </div>
          )}

          {/* Processing State */}
          {state === 'processing' && (
            <div className="text-center py-8 space-y-4">
              <Spinner size="lg" />
              <div>
                <p className="text-lg font-medium text-gray-900">Processing...</p>
                <p className="text-sm text-gray-500 mt-1">
                  Filling answers and calculating confidence scores
                </p>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div className="bg-blue-600 h-2 rounded-full animate-pulse" style={{ width: '60%' }} />
              </div>
            </div>
          )}

          {/* Ready State */}
          {state === 'ready' && result && (
            <div className="space-y-6">
              <div className="text-center py-4">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 mb-4">
                  <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h2 className="text-xl font-semibold text-gray-900">Ready to Download</h2>
                <p className="text-gray-500 mt-1">Your questionnaire has been filled</p>
              </div>

              {/* Summary Stats */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-700 mb-3">Summary</h3>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Total Questions:</span>
                    <span className="font-medium">{result.total_questions}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-green-600">High Confidence:</span>
                    <span className="font-medium text-green-600">{result.summary.high}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-yellow-600">Medium Confidence:</span>
                    <span className="font-medium text-yellow-600">{result.summary.medium}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-orange-600">Low Confidence:</span>
                    <span className="font-medium text-orange-600">{result.summary.low}</span>
                  </div>
                  <div className="flex justify-between col-span-2">
                    <span className="text-red-600">Requires Human Attention:</span>
                    <span className="font-medium text-red-600">{result.summary.requires_human_attention}</span>
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <button
                  onClick={handleDownload}
                  className="w-full py-3 px-4 rounded-lg font-medium text-white bg-green-600 hover:bg-green-700 transition-colors flex items-center justify-center gap-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Download Filled CSV
                </button>

                <button
                  onClick={handleReset}
                  className="w-full py-3 px-4 rounded-lg font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 transition-colors"
                >
                  Fill Another Questionnaire
                </button>
              </div>
            </div>
          )}

          {/* Error State */}
          {state === 'error' && (
            <div className="space-y-6">
              <div className="text-center py-4">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-100 mb-4">
                  <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </div>
                <h2 className="text-xl font-semibold text-gray-900">Something went wrong</h2>
                <p className="text-red-600 mt-2 text-sm">{error}</p>
              </div>

              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm">
                <h3 className="font-medium text-yellow-800 mb-2">Troubleshooting</h3>
                <ul className="text-yellow-700 space-y-1 list-disc list-inside">
                  <li>Is the backend running on 127.0.0.1:8000?</li>
                  <li>Try checking the API status below</li>
                  <li>Make sure you uploaded a valid CSV file</li>
                </ul>
              </div>

              <button
                onClick={handleReset}
                className="w-full py-3 px-4 rounded-lg font-medium text-white bg-blue-600 hover:bg-blue-700 transition-colors"
              >
                Try Again
              </button>
            </div>
          )}
        </div>

        {/* API Status Link */}
        <div className="mt-6 text-center">
          <button
            onClick={handleCheckHealth}
            className="text-sm text-gray-500 hover:text-gray-700 underline"
          >
            View API Status
          </button>

          {showHealth && (
            <div className="mt-3 p-3 bg-white rounded-lg border border-gray-200 text-sm">
              {healthStatus ? (
                <div className="flex items-center justify-center gap-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
                  <span className="text-green-700">
                    API Healthy - {healthStatus.knowledge_base_entries} knowledge base entries
                  </span>
                </div>
              ) : (
                <div className="flex items-center justify-center gap-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-red-500" />
                  <span className="text-red-700">API Unavailable - Check if backend is running</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <p className="mt-8 text-center text-xs text-gray-400">
          Bank Questionnaire Autofill Agent v1.0
        </p>
      </div>
    </main>
  );
}
