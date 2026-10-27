'use client'

import React, { useState, useEffect, useRef } from 'react';

// --- 1. TYPE DEFINITIONS & CONSTANTS ---

// Define the shape of the data extracted by the backend AI
interface ExtractedData {
    fullName: string;
    npi: string;
    dateOfBirth: string; // YYYY-MM-DD
    homeAddress: string;
    txLicenseNumber: string;
    federalDEANumber: string;
    deaExpires: string; // New field from CV (Page 3)
    medicalSchool: string; // New field from CV (Page 2)
    malpracticeCarrier: string; // New field from CV (Page 5)
    hasMalpractice: boolean;
    malpracticeSummary: string;
}

// Define the shape of a chat message
interface ChatMessage {
    id: number;
    sender: 'user' | 'system';
    text: string;
}

// CONSTANTS for Time Saved Calculation
const AVG_HUMAN_FILL_MINUTES = 90; // Average human time to fill the form (based on industry reports)
const AI_FILL_MINUTES = 1;         // Simulated AI time to extract and fill

// --- 2. MOCK AI OUTPUT (Extracted from CV Mehra and Weehope Fields) ---
const MOCK_AI_OUTPUT_JSON: ExtractedData = {
    fullName: "Sanjay Rajiv Mehra, MD",
    npi: "1780953210",
    dateOfBirth: "1978-06-17",
    homeAddress: "3821 Hightower Dr, Dallas, TX 75228",
    txLicenseNumber: "TX123456",
    federalDEANumber: "FM5482639",
    deaExpires: "2026-06-29", // Mocked date derived from CV
    medicalSchool: "All India Institute of Medical Sciences (AIIMS)",
    malpracticeCarrier: "Med Coverage Solutions, Inc.",
    hasMalpractice: true,
    malpracticeSummary: "Delayed diagnosis of a subarachnoid hemorrhage. Settled out of court for $425,000.",
};

// --- 3. MAIN APP COMPONENT ---

const FormPage: React.FC = () => {
    // --- STATE MANAGEMENT ---
    const [isProcessing, setIsProcessing] = useState(false);
    const [isContentVisible, setIsContentVisible] = useState(false);
    const [isSubmitted, setIsSubmitted] = useState(false); // NEW: Submission status
    const [timeSaved, setTimeSaved] = useState(0);         // NEW: Calculated time saved
    const [extractedData, setExtractedData] = useState<ExtractedData | null>(null);
    const [validationMessages, setValidationMessages] = useState<string[]>([]);
    const [chatLog, setChatLog] = useState<ChatMessage[]>([]);
    const [chatInput, setChatInput] = useState('');
    const [mainFile, setMainFile] = useState<File | null>(null);
    const [supportUrl, setSupportUrl] = useState('');
    const [urlStatus, setUrlStatus] = useState<'pending' | 'success' | 'error' | null>(null);

    const formRef = useRef<HTMLFormElement>(null);
    const chatLogRef = useRef<HTMLDivElement>(null);

    // Scroll chat to bottom on update
    useEffect(() => {
        if (chatLogRef.current) {
            chatLogRef.current.scrollTop = chatLogRef.current.scrollHeight;
        }
    }, [chatLog]);


    // --- UI Utilities ---

    const addMessage = (sender: 'user' | 'system', text: string) => {
        setChatLog(prev => [...prev, { id: Date.now(), sender, text }]);
    };

    // --- FILE & URL HANDLING ---

    const checkUrl = () => {
        if (!supportUrl.trim()) {
            setUrlStatus('error');
            return;
        }

        setUrlStatus('pending');
        const isMockSuccess = supportUrl.includes('valid') || supportUrl.includes('license');

        setTimeout(() => {
            setUrlStatus(isMockSuccess ? 'success' : 'error');
        }, 1000);
    };


    // --- AI WORKFLOW SIMULATION ---

    const processFiles = () => {
        if (!mainFile) {
            alert('Please upload the Mandatory Provider Document (File 1) to start extraction.');
            return;
        }

        setIsProcessing(true);
        setIsSubmitted(false); // Reset submission status on new process
        
        // Simulate API call delay
        setTimeout(() => {
            const data = MOCK_AI_OUTPUT_JSON;
            setExtractedData(data);

            setTimeout(() => {
                runValidation();
                setIsProcessing(false);
                setIsContentVisible(true);
            }, 1000);
        }, 2000);
    };

    // --- AUTO-FILL EFFECT ---
    useEffect(() => {
        if (extractedData && formRef.current) {
            const form = formRef.current;
            
            // Personal Data (Page 2)
            (form.elements.namedItem('fullName') as HTMLInputElement).value = extractedData.fullName || '';
            (form.elements.namedItem('npi') as HTMLInputElement).value = extractedData.npi || '';
            (form.elements.namedItem('dob') as HTMLInputElement).value = extractedData.dateOfBirth || ''; 
            (form.elements.namedItem('localResidence') as HTMLInputElement).value = extractedData.homeAddress || '';
            
            // Licensing & Registration (Page 3/4)
            (form.elements.namedItem('txLicenseNumber') as HTMLInputElement).value = extractedData.txLicenseNumber || '';
            (form.elements.namedItem('federalDEANumber') as HTMLInputElement).value = extractedData.federalDEANumber || '';
            (form.elements.namedItem('deaExpires') as HTMLInputElement).value = extractedData.deaExpires || '';
            
            // Education (Page 5)
            (form.elements.namedItem('medicalSchool') as HTMLInputElement).value = extractedData.medicalSchool || '';
            
            // Professional Liability (Page 13)
            (form.elements.namedItem('presentCarrier') as HTMLInputElement).value = extractedData.malpracticeCarrier || '';


            // Handle Malpractice radio button and summary (Page 16)
            const malpracticeYes = form.elements.namedItem('malpractice-yes') as HTMLInputElement;
            const malpracticeNo = form.elements.namedItem('malpractice-no') as HTMLInputElement;
            const malpracticeSummary = document.getElementById('malpractice-summary');
            const malpracticeValidationDiv = document.getElementById('malpractice-validation');

            if (extractedData.hasMalpractice) {
                if (malpracticeYes) malpracticeYes.checked = true;
                if (malpracticeNo) malpracticeNo.checked = false;
                if (malpracticeSummary) malpracticeSummary.textContent = `AI Found: **${extractedData.malpracticeSummary}** (Flagged for Review)`;
                if (malpracticeValidationDiv) malpracticeValidationDiv.classList.add('border-red-500');
            } else {
                if (malpracticeYes) malpracticeYes.checked = false;
                if (malpracticeNo) malpracticeNo.checked = true;
                if (malpracticeSummary) malpracticeSummary.textContent = 'No prior malpractice found in documents.';
                if (malpracticeValidationDiv) malpracticeValidationDiv.classList.remove('border-red-500');
            }
        }
    }, [extractedData]);

    // --- VALIDATION ---
    const runValidation = () => {
        if (!formRef.current) return;
        
        const form = formRef.current;
        const requiredInputs = form.querySelectorAll('[data-required="true"]') as NodeListOf<HTMLInputElement>;
        let messages: string[] = [];
        let isValid = true;
        
        requiredInputs.forEach(input => {
            input.classList.remove('border-red-500', 'bg-red-50');
            if (!input.value.trim()) {
                isValid = false;
                input.classList.add('border-red-500', 'bg-red-50');
                const label = form.querySelector(`label[for="${input.id}"]`);
                if (label) {
                    messages.push(`Missing required field: ${label.textContent?.replace('*', '').trim()}`);
                }
            }
        });

        // Specific Validation Check: Malpractice requires attention if YES
        if ((form.elements.namedItem('malpractice-yes') as HTMLInputElement)?.checked) {
            messages.push("ACTION REQUIRED: Malpractice 'YES' is flagged. Ensure all necessary attachments are ready (Page 17 Worksheet).");
        }

        setValidationMessages(messages);
        return messages.length === 0;
    };


    // --- CHAT LOGIC ---
    const handleChatSend = () => {
        const text = chatInput.trim();
        if (text) {
            addMessage('user', text);
            setChatInput('');

            setTimeout(() => {
                let response;
                if (text.toLowerCase().includes('malpractice')) {
                    response = "System: The Malpractice Worksheet was auto-generated using CV data and attached for review. Please approve section 57.";
                } else if (text.toLowerCase().includes('license')) {
                     response = "System: TX License was verified against the mock database and is valid until 06/30/2026.";
                } else {
                    response = "AI Agent: Thank you for your feedback. Forwarding to the compliance team.";
                }
                addMessage('system', response);
            }, 1500);
        }
    };

    // --- FINAL ACTIONS ---
    const saveAction = (actionType: 'SAVE' | 'SAVE_AND_NEXT' | 'SAVE_AND_EXIT') => {
        const isValid = runValidation(); 

        let message = '';
        let title = 'Save Action';

        if (!isValid && actionType !== 'SAVE') {
            alert('Cannot proceed: Please fix validation errors before approving or exiting.');
            return;
        }

        switch (actionType) {
            case 'SAVE':
                message = 'Current form data saved as Draft to the backend API.';
                break;
            case 'SAVE_AND_EXIT':
                message = 'Form data saved. Application session closed.';
                title = 'Session Closed';
                break;
            case 'SAVE_AND_NEXT':
                // Final submission flow
                message = 'Form data saved, approved, and successfully submitted! Proceeding to the next provider.';
                title = 'Submission Complete';
                
                // Calculate Time Saved
                const saved = AVG_HUMAN_FILL_MINUTES - AI_FILL_MINUTES;
                setTimeSaved(saved);
                
                // Set Submission Status
                setIsSubmitted(true);
                break;
        }

        alert(`${title}: ${message}`);
    };
    
    const downloadForm = () => {
        alert('Download Complete: Filled PDF (Weehope Credentialing Form - Dr. Mehra) downloaded successfully!');
    };
    
    // --- NEW: Time Saved Display Component ---
    const TimeSavedDisplay: React.FC = () => {
        return (
            <div className="bg-green-50 p-6 rounded-xl shadow-lg border-2 border-green-400">
                <h2 className="text-xl font-bold text-center text-green-700 mb-2">
                    ✅ Submission Completed
                </h2>
                <div className="text-center">
                    <p className="text-3xl font-extrabold text-green-600">
                        {timeSaved} Minutes
                    </p>
                    <p className="text-sm text-gray-600 mt-1">
                        Time Saved Per Form
                    </p>
                    <p className="text-xs text-gray-500 mt-2">
                        (Human Avg: {AVG_HUMAN_FILL_MINUTES} min - AI Processing: {AI_FILL_MINUTES} min)
                    </p>
                </div>
            </div>
        );
    };

    // --- RENDER HELPERS ---

    const renderUrlStatus = () => {
        if (urlStatus === 'pending') {
            return <p className="text-xs mt-1 text-gray-500">Checking URL reachability...</p>;
        } else if (urlStatus === 'success') {
            return <p className="text-xs mt-1 text-green-600">URL is reachable and appears valid.</p>;
        } else if (urlStatus === 'error') {
            return <p className="text-xs mt-1 text-red-600">URL check failed (CORS/404 simulated). Proceeding without it.</p>;
        }
        return <p id="status-url" className="text-xs mt-1 text-gray-500"></p>;
    };

    const renderValidationSummary = () => {
        if (validationMessages.length > 0) {
            return (
                <div className="bg-red-100 border border-red-400 text-red-800 p-3 rounded-lg mb-4 text-sm font-medium">
                    <strong>Validation Issues Found:</strong>
                    <ul className="list-disc pl-5 mt-1">
                        {validationMessages.map((msg, index) => <li key={index}>{msg}</li>)}
                    </ul>
                </div>
            );
        } else if (isContentVisible && !isProcessing) {
            return (
                <div className="bg-green-100 border border-green-400 text-green-800 p-3 rounded-lg mb-4 text-sm font-medium">
                    <strong>Validation Success:</strong> All mandatory fields filled and no critical issues flagged.
                </div>
            );
        }
        return null;
    };

    // --- MAIN RENDER ---
    return (
        <div id="app" className="p-4 md:p-8 space-y-8">
            {/* TOP SECTION: Upload Controls and Status */}
            <div id="control-panel" className="bg-white p-6 rounded-xl shadow-2xl space-y-4">
                <h1 className="text-3xl font-extrabold text-blue-800 text-center">AI Agent Input & Validation</h1>
                <p className="text-center text-gray-600">Upload provider documents to initiate AI extraction and form auto-fill.</p>
                
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-4 border-t">
                    
                    {/* UPLOAD SECTION 1: Mandatory Provider File (CV) */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">1. Mandatory: Provider Document (e.g., CV)</label>
                        <input 
                            type="file" 
                            id="upload-main" 
                            accept=".pdf,.jpg,.png" 
                            onChange={(e) => setMainFile(e.target.files ? e.target.files[0] : null)}
                            className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-10" 
                        />
                        <p id="status-main" className="text-xs mt-1 text-gray-500">
                            {mainFile ? `Selected: ${mainFile.name}` : 'No file selected.'}
                        </p>
                    </div>
                    
                    {/* UPLOAD SECTION 2: Optional Supporting Documents (File or URL) */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">2. Optional: Supporting Documents</label>
                        <input 
                            type="file" 
                            id="upload-support" 
                            accept=".pdf,.jpg,.png" 
                            className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-green-50 file:text-green-700 hover:file:bg-green-10" 
                        />
                        
                        <div className="mt-3">
                            <label htmlFor="support-url" className="block text-xs font-medium text-gray-500 mb-1">... or enter URL (Optional)</label>
                            <div className="flex space-x-2">
                                <input 
                                    type="url" 
                                    id="support-url" 
                                    placeholder="https://external-license-site.com" 
                                    value={supportUrl}
                                    onChange={(e) => setSupportUrl(e.target.value)}
                                    className={`p-2 border rounded-lg w-full text-sm focus:ring-green-500 ${
                                        urlStatus === 'error' ? 'border-red-500' : 'border-gray-300 focus:border-green-500'
                                    }`} 
                                />
                                <button 
                                    onClick={checkUrl} 
                                    disabled={isProcessing}
                                    className="bg-gray-200 text-gray-700 px-3 py-1.5 rounded-lg text-sm hover:bg-gray-300 transition-colors disabled:opacity-50"
                                >
                                    {urlStatus === 'pending' ? '...' : 'Check'}
                                </button>
                            </div>
                            {renderUrlStatus()}
                        </div>
                    </div>
                </div>

                <div className="flex justify-center pt-4">
                    <button 
                        onClick={processFiles} 
                        id="process-btn" 
                        disabled={isProcessing}
                        className={`px-8 py-3 font-bold rounded-xl shadow-lg transition-transform transform hover:scale-[1.01] disabled:bg-gray-400 ${
                            isProcessing ? 'bg-orange-500' : (isContentVisible ? 'bg-green-600' : 'bg-indigo-600 hover:bg-indigo-700')
                        }`}
                    >
                        {isProcessing ? '🤖 AI Processing...' : (isContentVisible ? '✅ Extraction Complete' : '🚀 Upload & Start AI Extraction')}
                    </button>
                </div>
            </div>

            {/* MAIN CONTENT: Split View */}
            <div id="main-content" className={`${isContentVisible ? 'grid' : 'hidden'} main-grid gap-8 pt-4`}>

                {/* LEFT PANEL: Controls, Chat, and Download */}
                <div className="space-y-6">
                    
                    {/* Time Saved Display (NEW) */}
                    {isSubmitted ? (
                        <TimeSavedDisplay />
                    ) : (
                        <div className="bg-white p-6 rounded-xl shadow-lg text-center">
                            <h2 className="text-xl font-semibold mb-3 text-blue-700">Form Generation Complete</h2>
                            <button 
                                id="download-btn" 
                                onClick={downloadForm} 
                                className="w-full px-6 py-3 bg-purple-600 text-white font-bold rounded-lg shadow-xl hover:bg-purple-700 transition-colors"
                            >
                                ⬇️ Download Filled Form
                            </button>
                        </div>
                    )}
                    

                    {/* Chat Simulation */}
                    <div className="bg-white p-6 rounded-xl shadow-lg">
                        <h2 className="text-xl font-semibold mb-4 text-gray-800">Reviewer Chat & Feedback</h2>
                        <div ref={chatLogRef} className="h-64 overflow-y-auto border p-3 rounded-lg bg-gray-50 space-y-3 text-sm">
                            {chatLog.map((msg) => (
                                <div key={msg.id} className={msg.sender === 'user' ? 'text-right' : 'text-left'}>
                                    <span className={`inline-block p-2 rounded-lg max-w-xs ${
                                        msg.sender === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-800'
                                    }`}>
                                        {msg.text}
                                    </span>
                                </div>
                            ))}
                        </div>
                        <div className="mt-4 flex space-x-2">
                            <input 
                                type="text" 
                                id="chat-input" 
                                placeholder="Enter feedback or question..." 
                                value={chatInput}
                                onChange={(e) => setChatInput(e.target.value)}
                                onKeyPress={(e) => { if (e.key === 'Enter') handleChatSend(); }}
                                className="p-2 border border-gray-300 rounded-lg w-full focus:border-blue-500 focus:ring-blue-500" 
                            />
                            <button 
                                onClick={handleChatSend} 
                                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
                            >
                                Send
                            </button>
                        </div>
                    </div>

                    {/* Save Actions */}
                    <div className="bg-white p-6 rounded-xl shadow-lg">
                        <h2 className="text-xl font-semibold mb-3 text-gray-800">Final Review Actions</h2>
                        <div className="space-y-3">
                            <button onClick={() => saveAction('SAVE')} className="w-full px-4 py-2 bg-yellow-500 text-white font-bold rounded-lg hover:bg-yellow-600 transition-colors" disabled={isSubmitted}>
                                💾 SAVE (Draft)
                            </button>
                            <button onClick={() => saveAction('SAVE_AND_NEXT')} className="w-full px-4 py-2 bg-green-500 text-white font-bold rounded-lg hover:bg-green-600 transition-colors" disabled={isSubmitted}>
                                ✅ SAVE AND NEXT (Approve)
                            </button>
                            <button onClick={() => saveAction('SAVE_AND_EXIT')} className="w-full px-4 py-2 bg-red-500 text-white font-bold rounded-lg hover:bg-red-600 transition-colors" disabled={isSubmitted}>
                                🚪 SAVE AND EXIT
                            </button>
                        </div>
                    </div>
                </div>

                {/* RIGHT PANEL: Auto-Filled Form & Validation */}
                <div id="form-container" className="bg-white p-6 rounded-xl shadow-2xl lg:col-span-2">
                    <h2 className="text-2xl font-bold mb-4 text-center text-blue-800">Weehope Umakeit Credentialing App (Auto-Filled)</h2>
                    {renderValidationSummary()}
                    <form id="credentialing-form" ref={formRef} className="space-y-6 scrollable-content">
                        
                        <h3 className="text-xl font-semibold text-gray-700 border-b pb-2">PERSONAL DATA (Page 2)</h3>
                        
                        {/* Q.1 Name */}
                        <div className="required-field">
                            <label htmlFor="fullName" className="block text-sm font-medium text-gray-700">1. Name *</label>
                            <input type="text" id="fullName" name="fullName" className="mt-1 block w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500" data-required="true" onChange={runValidation} />
                        </div>

                        {/* Q.3 SSN (Mock field, since SSN is sensitive) */}
                        <div>
                            <label htmlFor="ssn" className="block text-sm font-medium text-gray-700">3. Social Security Number</label>
                            <input type="text" id="ssn" name="ssn" placeholder="XXX-XX-9076 (Mocked)" className="mt-1 block w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500" onChange={runValidation} />
                        </div>

                        {/* Q.4 NPI */}
                        <div className="required-field">
                            <label htmlFor="npi" className="block text-sm font-medium text-gray-700">4. NPI (National Provider Identifier) *</label>
                            <input type="text" id="npi" name="npi" className="mt-1 block w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500" data-required="true" onChange={runValidation} />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                             {/* Q.5 Date of Birth */}
                            <div className="required-field">
                                <label htmlFor="dob" className="block text-sm font-medium text-gray-700">5. Date of Birth *</label>
                                <input type="date" id="dob" name="dob" className="mt-1 block w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500" data-required="true" onChange={runValidation} />
                            </div>
                            {/* Q.7 Citizenship */}
                            <div>
                                <label htmlFor="citizenship" className="block text-sm font-medium text-gray-700">7. Citizenship</label>
                                <input type="text" id="citizenship" name="citizenship" value="United States" readOnly className="mt-1 block w-full p-2 border border-gray-300 rounded-md bg-gray-100 text-gray-600" />
                            </div>
                        </div>

                        {/* Q.10 Local Residence */}
                        <div>
                            <label htmlFor="localResidence" className="block text-sm font-medium text-gray-700">10. Local Residence (REQUIRED)</label>
                            <input type="text" id="localResidence" name="localResidence" className="mt-1 block w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500" onChange={runValidation} />
                        </div>

                        <h3 className="text-xl font-semibold text-gray-700 border-b pb-2 mt-8">EDUCATION/TRAINING (Page 4-6)</h3>

                        {/* Q.22 Medical/Dental/AHP Education */}
                        <div className="required-field">
                            <label htmlFor="medicalSchool" className="block text-sm font-medium text-gray-700">22. Medical/Dental/AHP Education (Facility Name) *</label>
                            <input type="text" id="medicalSchool" name="medicalSchool" className="mt-1 block w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500" data-required="true" onChange={runValidation} />
                        </div>
                        
                        <h3 className="text-xl font-semibold text-gray-700 border-b pb-2 mt-8">PROFESSIONAL LICENSES & DEA (Page 3/4)</h3>
                        
                        {/* Q.17 Texas Medical license No. */}
                        <div className="required-field">
                            <label htmlFor="txLicenseNumber" className="block text-sm font-medium text-gray-700">17. Texas Medical license No. *</label>
                            <input type="text" id="txLicenseNumber" name="txLicenseNumber" className="mt-1 block w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500" data-required="true" onChange={runValidation} />
                        </div>

                        {/* Q.18 Federal DEA Registration No. */}
                        <div className="required-field">
                            <label htmlFor="federalDEANumber" className="block text-sm font-medium text-gray-700">18. Federal DEA Registration No. *</label>
                            <input type="text" id="federalDEANumber" name="federalDEANumber" className="mt-1 block w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500" data-required="true" onChange={runValidation} />
                        </div>

                        {/* Q.18 DEA Date Expires */}
                        <div>
                            <label htmlFor="deaExpires" className="block text-sm font-medium text-gray-700">18. DEA Date Expires</label>
                            <input type="date" id="deaExpires" name="deaExpires" className="mt-1 block w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500" onChange={runValidation} />
                        </div>

                        <h3 className="text-xl font-semibold text-gray-700 border-b pb-2 mt-8">PROFESSIONAL LIABILITY (Page 13)</h3>
                        
                        {/* Q.48 Present Carrier for Texas Practice */}
                        <div>
                            <label htmlFor="presentCarrier" className="block text-sm font-medium text-gray-700">48. Present Carrier for Texas Practice</label>
                            <input type="text" id="presentCarrier" name="presentCarrier" className="mt-1 block w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500" onChange={runValidation} />
                        </div>

                        <h3 className="text-xl font-semibold text-gray-700 border-b pb-2 mt-8">PRACTITIONER QUESTIONNAIRE (Page 16)</h3>

                        {/* Q.57 J(2) Malpractice History Checkbox */}
                        <div id="malpractice-validation" className="p-4 rounded-lg bg-gray-50 border border-gray-300">
                            <label className="block text-sm font-medium text-gray-700">57. J(2) Malpractice Claim Resulted in Settlement?</label>
                            <div className="mt-2 space-y-2">
                                <div className="flex items-center">
                                    <input id="malpractice-yes" type="radio" value="YES" name="malpractice" className="h-4 w-4 text-red-600 border-gray-300 focus:ring-red-500" onChange={runValidation} />
                                    <label htmlFor="malpractice-yes" className="ml-2 block text-sm font-medium text-gray-700">YES (AI detected settlement/judgment)</label>
                                </div>
                                <div className="flex items-center">
                                    <input id="malpractice-no" type="radio" value="NO" name="malpractice" className="h-4 w-4 text-green-600 border-gray-300 focus:ring-green-500" defaultChecked onChange={runValidation} />
                                    <label htmlFor="malpractice-no" className="ml-2 block text-sm font-medium text-gray-700">NO</label>
                                </div>
                            </div>
                            <p id="malpractice-summary" className="mt-3 text-xs p-2 rounded-md bg-red-100 text-red-800 border border-red-300">
                                AI Found: Malpractice summary will appear here.
                            </p>
                        </div>

                    </form>
                </div>
            </div>
        </div>
    );
};

export default FormPage;
