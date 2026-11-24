# **Project: Intelligible Blackboard Architecture with Counterfactual Agents**

##  **Project Overview & Context**

Traditional multi-agent systems often rely on linear communication chains where models pass text instructions sequentially from one to another. These architectures are highly brittle and frequently suffer from context degradation and severe "telephone game" errors over long-horizon tasks. To resolve this infrastructural bottleneck, the Blackboard Architecture centralizes agent interactions around a globally shared, structured state object. Instead of direct message passing, agents act asynchronously and react dynamically to changes on a central "blackboard".

This project advances the blackboard paradigm by incorporating two frontier concepts in explainable AI (XAI) and multi-agent coordination: the Two-Way Intelligibility Protocol (PXP) formalized by Baskar et al. and retrospective counterfactual reasoning. The PXP protocol governs interactions between "PEX agents"—agents capable of providing both a prediction ("what") and an underlying explanation ("why"). Concurrently, a designated proportion of these agents will possess the capacity to execute counterfactual credit self-assessments. When the system encounters deadlocks or conflicting assertions on the board, these specialized agents evaluate their historical decisions by asking: *"If I had communicated an alternative explanation or tag in the past, would the global blackboard state be closer to consensus now?"*

Upon successful completion, students would have learnt about:

> * **PXP Blackboard Implementation**: Construct a thread-safe central state store configured to process structured communication using Baskar et al.'s two-way intelligibility syntax.  
> * **Counterfactual Reflection Engine**: Develop a local retrospective sandbox module that allows selected agents to evaluate prior steps and perform credit assignment optimization to break reasoning loops.  
> * **Real-Time Visualization UI**: Build an interactive web-based dashboard that visually traces state modifications on the blackboard, highlights agent activation patterns, and plots reasoning streams in real time.  
> * **Ablation Performance Profiling**: Systematically vary the proportion of counterfactual-enabled agents within the system (e.g., 0%, 33%, 66%, 100%) to study its empirical impact on consensus accuracy and deadlocks.  
> * **Standardized Benchmark Validation**: Validate the framework using modern public datasets designed for multi-agent discovery and multi-stage collaborative reasoning, including KramaBench and MSCoRe.

## **Methodology & System Architecture**

The system consists of four decoupled operational layers designed to support efficient inference on consumer-grade hardware. Communication between agents and the blackboard will use the PXP Intelligibility Protocol (possibly simplified for convenience).

## **A. The PXP-Governed Board (Communication Layer)**

Rather than writing free-form strings, agents update the board by pairing their domain-specific predictions and explanations with strict message-tags defined by the PXP protocol:

> * **RATIFY**: The agent reviews a current hypothesis on the board and formally aligns with both its prediction and explanation.  
> * **REVISE**: The agent alters its own local prompt context or data parameters to accommodate the board's updates and writes an adjusted thesis back to the store.  
> * **REFUTE**: The agent rejects the current board position but cannot adjust its internal knowledge base to correct it, logging a logical roadblock.  
> * **REJECT**: The agent completely conflicts with the target prediction and explanation matrix.

The central controller monitors the execution stream of these tags to mathematically classify whether a session achieves "Strong" or "Ultra-Strong" Intelligibility.

## **B. The Retrospective Credit Assignment Layer (Reasoning Layer)**

When the blackboard experiences a continuous loop of REFUTE or REJECT tags, standard systems crash or exhaust their token limits. In this framework, agents equipped with counterfactual capabilities intercept the deadlock. The agent copies the historical log of the blackboard into an isolated local memory block and runs a retrospective simulation. It modifies its past outputs to determine if a different initial tag or an alternative wording of its explanation would have steered the other agents away from the deadlock. The resulting delta is used to adjust its active system prompt or modify its voting weights on the live blackboard to break the system standstill.

## **C. The Deterministic Scheduler (Control Layer)**

An event-driven algorithmic controller monitors modifications to the blackboard. It evaluates which specialized sub-agent possesses the highest priority to act based on the latest PXP tags, enforces concurrency limits to prevent writing collisions, and determines terminal boundaries when a stable consensus or an unresolvable impasse is reached.

## **D. Real-Time State & Agent Visualization Matrix (UI Layer)**

To provide operational transparency, a lightweight front-end application hooks into the central control layer via persistent web sockets. This UI translates the internal database logs into a visual graph. The current problem space is represented as a centralized root node, and incoming agent assertions branch outward dynamically based on their PXP tags. Color-coded markers instantly flag system bottlenecks (e.g., flashing red for cascading REJECT trends), while a dedicated split-panel tracking layout surfaces when an agent initiates an internal counterfactual rollback simulation, rendering the "alternative timeline" alongside the live system run.

## **Experimental Design & Evaluation Metrics**

To measure the true utility of counterfactual thinking in an explainable multi-agent system, students will execute an ablation study across the following independent configurations:

> * **Control Group**: 100% standard PEX agents (0% counterfactual capability).  
> * **Experimental Group A**: 33% counterfactual agents, 66% standard PEX agents.  
> * **Experimental Group B**: 66% counterfactual agents, 34% standard PEX agents.  
> * **Experimental Group C**: 100% counterfactual agents.

For each configuration, the system will run 500 distinct trials across selected benchmarks to measure three primary dependent variables:

> 1. **Convergence Success Rate**: The percentage of test instances where the agents successfully resolve disagreements and converge on a unified, accurate answer without exceeding maximum iteration thresholds.  
> 2. **Intelligibility Depth Mapping**: The ratio of sessions concluding in "Ultra-Strong" Intelligibility (where productive REVISE loops occur) versus basic "Strong" or failed classifications.  
> 3. **Token Cost Analysis**: A comparison of total input/output tokens consumed per problem instance to verify if local counterfactual simulations save overall API or compute costs by truncating extended multi-agent debates on the live board.

## **Benchmarking Datasets**

The architecture will be evaluated against three prominent open-source datasets to guarantee cross-domain reliability:

> * **KramaBench (2025)**: The foundational public benchmark built explicitly to measure data and information discovery using multi-agent blackboard systems.  
> * **MSCoRe (Multi-Stage Collaborative Reasoning, 2025\)**: A dataset featuring over 126,000 domain-specific QA items across automotive, pharmaceutical, and energy systems, ideal for testing complex, multi-step explanation alignment.  
> * **MedAgentBench (2025)**: An interactive medical application environment providing 100 highly complex clinical reasoning tasks to benchmark panel consensus frameworks.

## **Team Roles & Division of Labor**

The technical workload is distributed symmetrically across a three-student team based on core software boundaries:

| Student Role | Primary Responsibilities | Core Deliverables |
| :---- | :---- | :---- |
| **Student 1: Infrastructure & Protocol Control Engineer** | Focuses on the core blackboard data store, state serialization, and parsing the PXP protocol tags. | \- Central thread-safe Blackboard repository. \- PXP message-tag validator and state transition machine. \- Event-driven scheduling loop and priority arbiter. |
| **Student 2: Agent Engineering & Counterfactual Architect** | Focuses on designing the local LLM wrappers, system prompts, and the isolated retrospective sandbox. | \- Base LLM instrumentation code (leveraging local 7B models). \- Prompt libraries optimized for generating PEX explanations. \- Retrospective credit simulation module for counterfactual rollbacks. |
| **Student 3: Front-End UI & Benchmarking Specialist** | Responsible for web socket data streaming, interactive UI rendering, dataset ingest pipelines, and metric analysis. | \- Streaming web socket server and dynamic React/D3 node graph front-end. \- Ingest parsers for KramaBench, MSCoRe, and MedAgentBench. \- Token counter, cost calculator, and convergence tracking tools. |

## 

##  **Project Milestones**

> * **Milestone 1 (Weeks**: Initialize the central blackboard repository and verify the event-driven control scheduler can process basic RATIFY and REJECT state changes smoothly.  
> * **Milestone 2**: Connect local 7B-parameter models to the pipeline. Complete the prompt libraries to ensure agents consistently emit correctly formatted predictions and structured explanations. Establish basic web socket connectivity between the core backend and the visualization app.  
> * **Milestone 3**: Deploy the retrospective counterfactual simulation module. Introduce a synthetic deadlock to verify an agent can copy the board state, roll back steps in memory, and rewrite its prompt instructions to successfully alter outcomes. Build out the frontend dynamic graph layout to visualize these simulation steps.  
> * **Milestone 4**: Execute the automated benchmarking batches across KramaBench, MSCoRe, and MedAgentBench. Compile token efficiency graphs within the UI analytics board and submit the final research paper detailing the ablation findings.

## **Key Software Deliverables**

The project should result in four  highly integrated software artifacts:

## **A. Thread-Safe Blackboard Core & PXP State Controller**

> * **State Encapsulation Engine**: A transactional, concurrent JSON/Redis-backed data repository representing the global blackboard space.  
> * **PXP Grammatical Parser**: Python validation modules that enforce structural input schemas, verifying that all incoming agent data features compliant PXP execution strings (RATIFY, REVISE, etc.).  
> * **Priority Scheduler**: An event-driven execution harness that continuously reads state deltas and scores agent activation queues.

## **B. Local LLM Broker & Counterfactual Simulation Sandbox**

> * **Model Inference Harness**: Multi-threaded model wrapper classes using open-source utilities (e.g., Hugging Face or vLLM) to drive small 7B parameter models efficiently.  
> * **Retrospective Rollback Sandbox**: An isolated scratchpad utility that allows agents to clone a slice of historical board logs, manipulate prior inputs, and execute simulated forward passes to optimize credit assignment.  
> * **Prompt Matrix Library**: A structured prompt configuration directory mapping narrow expert personas (e.g., specialized medical or data analysis fields) to explicit JSON schema constraints.

## **C. Web-Based Real-Time Blackboard Visualization Suite**

> * **Streaming Socket Interface**: A fast backend server layer (FastAPI/WebSockets) that exposes live streams of blackboard state logs, tag transitions, and agent queues.  
> * **Interactive Dynamic UI**: A responsive browser front-end (React or Vue with D3.js/Vis.js) displaying an animated, network-graph layout of the blackboard. It tracks reasoning nodes, highlights active agent states, and maps side-by-side comparative views of counterfactual simulations.  
> * **Control Inspector Controls**: In-browser inspection tools enabling students to step forward or backward through the agent loop execution history manually.

## **D. Automated Benchmark & Analytics Engine**

> * **Dataset Processing Ingestors**: Extractors and loaders that clean, convert, and stream test records from KramaBench, MSCoRe, and MedAgentBench into the blackboard environment.  
> * **Statistical Metrics Tracker**: Programmatic instrumentation code tracking running token tallies, computing execution cycle counts, and logging convergence success criteria.  
> * **Ablation Plotting Toolkit**: Automated data plotting scripts parsing trial output CSV files to generate formatted accuracy vs. counterfactual density visualization charts.

