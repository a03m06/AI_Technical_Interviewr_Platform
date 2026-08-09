# AI Technical Interviewer

This is a full-stack AI-powered technical interview platform designed to simulate a real technical interview experience.

The main goal of the project is to provide an interactive interviewer that can conduct technical interviews across topics such as DSA, OOP, DBMS, Operating Systems, Machine Learning, and other computer science fundamentals. Instead of following a fixed list of questions, the system uses an LLM-powered workflow to generate relevant questions, evaluate candidate responses, ask contextual follow-up questions, and provide personalized feedback.

The project combines Retrieval-Augmented Generation (RAG) with an agent-based workflow so that the interview can use a curated technical knowledge base while still maintaining a dynamic and conversational interview flow.

## Features

- AI-powered technical interview simulation.
- Supports multiple technical domains including:
  - Data Structures & Algorithms
  - Object-Oriented Programming
  - Database Management Systems
  - Operating Systems
  - Machine Learning
  - Computer Science fundamentals
- Retrieval-Augmented Generation (RAG) for retrieving relevant technical knowledge.
- Dynamic technical question generation using an LLM.
- Context-aware follow-up questions based on previous responses.
- Automated evaluation of candidate answers.
- Personalized feedback based on interview performance.
- Interview scoring and performance tracking.
- Agent-based interview workflow using LangGraph.
- REST APIs connecting the frontend and backend.

## How the Interview Works

The interview follows a dynamic workflow instead of simply presenting a fixed set of questions.

```text
Candidate
    ↓
Select Interview Topic
    ↓
Interview Agent
    ↓
Retrieve Relevant Knowledge
    ↓
RAG
    ↓
LLM
    ↓
Generate Question
    ↓
Candidate Response
    ↓
Answer Evaluation
    ↓
Follow-up / Next Question
    ↓
Performance Analysis
    ↓
Personalized Feedback

The system retrieves relevant information from the technical knowledge base using RAG and provides the retrieved context to the LLM.

The LLM then uses this context along with the interview history to generate appropriate questions and evaluate the candidate's responses.

Based on the candidate's answer, the system can continue the interview with a relevant follow-up question rather than simply moving to a predetermined question.

Agent-Based Architecture

The interview workflow is orchestrated using LangGraph.

                    Interview Request
                           │
                           ▼
                    Interview Agent
                           │
                           ▼
                    Retrieve Context
                           │
                           ▼
                         RAG
                           │
                           ▼
                         LLM
                           │
                  ┌────────┴────────┐
                  ▼                 ▼
            Generate Question   Evaluate Answer
                  │                 │
                  └────────┬────────┘
                           ▼
                    Follow-up Decision
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              Follow-up      Next Question
                    │             │
                    └──────┬──────┘
                           ▼
                    Final Evaluation
                           │
                           ▼
                  Personalized Feedback
```
LangGraph is used to manage the different stages of the interview and maintain the flow between question generation, retrieval, answer evaluation, follow-up generation, and final feedback.

RAG Pipeline

The project uses Retrieval-Augmented Generation to ground the interview in relevant technical knowledge.

Technical Knowledge Base
          ↓
     Document Loading
          ↓
      Text Splitting
          ↓
       Embeddings
          ↓
     Vector Retrieval
          ↓
 Relevant Context
          ↓
          LLM
          ↓
Question / Evaluation / Feedback

This allows the system to retrieve relevant information before generating questions or evaluating responses instead of relying entirely on the LLM's internal knowledge.

Tech Stack
Frontend
React.js
Vite
JavaScript
HTML/CSS
Backend
Python
FastAPI
Uvicorn
REST APIs
Generative AI
LLM
LangChain
LangGraph
Retrieval-Augmented Generation (RAG)
Embeddings
Vector retrieval
Project Structure
AI-Technical-Interviewer/
│
├── frontend/
│   ├── src/
│   ├── components/
│   ├── pages/
│   ├── services/
│   └── ...
│
└── backend/
    ├── agents/
    ├── routes/
    ├── services/
    ├── rag/
    ├── ...
    └── requirements.txt
API

The backend exposes REST APIs consumed by the React frontend.

The APIs handle functionality such as:

Starting an interview
Generating interview questions
Retrieving relevant technical context
Submitting candidate responses
Evaluating answers
Generating follow-up questions
Calculating interview scores
Generating personalized feedback
Performance Evaluation

The system evaluates the candidate based on factors such as:

Technical correctness
Conceptual understanding
Problem-solving approach
Quality of explanation
Response relevance

The final analysis is used to generate personalized feedback and identify areas where the candidate can improve.

Environment Variables

Create a .env file in the backend and add the required API keys and configuration:

LLM_API_KEY=

Add any additional environment variables required by the selected LLM provider or vector retrieval system.

Do not commit API keys or other sensitive credentials to the repository.

Running the Project
Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

The backend will be available at:

http://127.0.0.1:8000

API documentation:

http://127.0.0.1:8000/docs
Frontend
cd frontend
npm install
npm run dev

The frontend will then be available through the Vite development server.

Project Objective

The project aims to make technical interview preparation more interactive and personalized.

Instead of repeatedly solving questions from static question lists, candidates can interact with an AI interviewer that can retrieve relevant technical knowledge, dynamically conduct the interview, evaluate responses, ask follow-up questions, and provide feedback based on their performance.

Author

Arshi Mittal
