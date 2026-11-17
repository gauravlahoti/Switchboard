# Reflex guided tour: narration script

Voice: Gaurav, first person, plain and unhurried. Recorded later with ElevenLabs.
Status: draft 1 for your edit. Nothing here has been recorded or rendered yet.

## How to read this

- **VO** is the exact text that goes to the voice engine. One VO paragraph is one audio clip.
- **{{slot}}** is a number measured from the recording. The build script fills it in and turns it into
  speech ("509 ms" becomes "about half a second"). The value in square brackets is a draft from my earlier
  live runs, only so you can judge the rhythm. It is replaced by the real measurement before any audio is made.
- **Thinking** says who is doing the work at that moment: Jev (System One), Gemini (System Two), code, or a person.
- **Trigger** is the recorded event the beat waits for. The narration follows the run, not a stopwatch.
- **[X]** marks the beats kept in the Express cut, about 6 minutes with the action.
- No em dashes anywhere (spec 90). Numbers are written as words so the voice does not misread digits.

Draft length: see the table at the end.

---

## Part 0. Cold open

### C0.1 The recipe [X]
- Trigger: tour start, the "food recipe" recording plays at 1x from the first message
- Screen: console full screen, the message is typed, the graph lights up in about a second, the reply and the
  "No model call" pill land. A large clock in the corner stops on the total.
- Thinking: Jev, then code
- VO: I just asked an IT help desk for a food recipe. It understood the request, judged it, and turned it down
  in {{decline_total}} [1.4 seconds]. No language model was called. Not one token was generated. Stay with me
  for a few minutes and you will see exactly how that works, and just as important, where this approach is the
  wrong one.

---

## Part 1. Two ways to think

### P1.1 The question
- Trigger: chapter start
- Screen: black. A long, friendly paragraph from a chatbot types out. A cursor tries to pull a field out of it,
  a bracket does not match, a small red spark, the paragraph dissolves into a clean `{ }`.
- Thinking: none (concept)
- VO: Language models have been superhuman at chat for years. So where is all the automation? TypeSafe's founder,
  Diogo Almeida, calls that his driving question. Here is my take. Chat is easy to be good at, because a person
  reads the answer. Automation is hard, because software has to read it. And software does not do well with prose.

### P1.2 Two speeds
- Trigger: after P1.1
- Screen: split screen over soft washes in the app's colours. Left: "2 x 2" and the answer "4" lands instantly with
  a tiny counter. Right: "17 x 24" with a slow, effortful counter and a flicker of working-out before "408".
  Labels fade in: System One in teal, System Two in violet.
- Thinking: none (concept)
- VO: Daniel Kahneman gave us a useful picture of how minds work. System One is fast and automatic. Two times two
  is four, and you do not work it out, you just know. System Two is slow and deliberate. Seventeen times twenty
  four, you have to stop and work through it. A good mind needs both, and knows which one to reach for.

### P1.3 The usual answer
- Trigger: after P1.2
- Screen: a customer email appears. It is sent into a violet "LLM" box, a JSON block comes out with a
  `"confidence": 0.9` field circled and labelled "a guess it writes about itself". A stopwatch and a cost meter run.
- Thinking: none (concept)
- VO: A lot of decisions inside software are quick judgment calls. The usual answer is to send them to a language
  model and ask for structured output. It works. But a language model is a System Two. It takes seconds, it costs
  money on every call, and it never tells you how sure it really was. You can ask for a confidence score, but that
  is a guess it writes about itself, not the probabilities it actually used.

### P1.4 Meet Jev [X]
- Trigger: after P1.3
- Screen: the same email, now as a "state" card, with the three questions as typed chips: Refund, yes or no.
  Team, a list. Urgency, a scale. Each flips to a real answer with a probability bar, from a recorded live Jev
  call on this exact email. A stamp: "no sentences".
- Thinking: Jev (recorded call)
- VO: Jev is a System One model, and TypeSafe say it is the first. Take a customer email: I was charged twice, I
  need my money back. Software needs three answers. Is it a refund? Which team gets it, billing or operations?
  How urgent is it? You hand Jev the email as state, and those three as typed questions. Each comes back as a
  probability. Refund, {{refund_p}} percent yes. Team, {{team_top}}, with a probability for every option.
  Urgency, a score from low to critical. No sentences. Jev does not write replies, produce code, or explain
  itself. That is the trade, and we will come back to it.

### P1.5 How it is trained
- Trigger: after P1.4
- Screen: a three-rung ladder. Rung one, "pretraining": text streams in, a next-word guess ticks. Rung two,
  "post training": two answers, a hand picks one; a green tick on a maths answer; a dial labelled "sure of
  itself" swinging too high. Rung three, "Jev": a calibration dial that settles on the diagonal. A last frame:
  tokens appearing one at a time on the left, all answers appearing at once on the right.
- Thinking: none (concept)
- VO: How do you train a model to give honest probabilities? Start with how language models learn. First they
  read a huge amount of text and learn to predict the next word. That is pretraining, and it is not yet good at
  talking. Then comes post training, with reinforcement learning. With human feedback, people pick the better of
  two answers, so the model learns to please them, and it can learn to sound sure of itself even when it is
  wrong. With verifiable rewards, the model is rewarded when a maths answer is right or the code passes its
  tests, but that only checks the final answer. Jev is trained a different way. TypeSafe call it reinforcement
  learning for calibrated decisions, and the reward is for honest probabilities. If Jev says twenty percent, that
  should happen about one time in five. And Jev does not write one word at a time. It produces all its answers in
  one parallel pass, which is why you can ask many questions at once.

### P1.6 Where it came from
- Trigger: after P1.5
- Screen: a quiet timeline strip: "two years in stealth", "September 15, 2026: Jev launches", "October 14, 2026:
  Jev 1.14". A Kahneman book silhouette and a steam engine line drawing, each with one short caption.
- Thinking: none (concept)
- VO: Where did it come from? TypeSafe launched Jev in September twenty twenty six, after two years in stealth.
  Its founder, Diogo Almeida, says he worked on the methods at OpenAI that taught language models to follow
  instructions, and the TypeSafe docs credit him as a co-inventor of RLHF. The name System One comes straight from
  Kahneman. Jev is named after William Stanley Jevons, the economist. His lesson from coal was that when steam
  engines got more efficient, demand went up, not down. TypeSafe expect the same for intelligence: every big drop
  in cost unlocks far more uses. Their stated mission is an interface that software can depend on.

### P1.7 Why we care
- Trigger: after P1.6
- Screen: three cards that fill with real numbers from the recordings as they are spoken. Speed and cost: Jev
  latency and cost per call against Gemini's. Control: a small truth table. Audit: one log line with a typed score.
- Thinking: Jev and code (concept)
- VO: So why should you care? Software needs System One thinking, and we keep handing it System Two. Three
  reasons. First, speed and cost. A Jev call in this demo takes {{jev_call_typical}} [a few hundred milliseconds]
  and costs {{jev_call_cost}} [a few thousandths of a cent]. I measured it, and I will show you. Second, control.
  Code owns the flow, and Jev supplies the judgments. Jev judges, code decides. Third, you can audit it. Every
  judgment is a number you can log, test, and put a threshold on, instead of a paragraph you hope you read
  correctly.

### P1.8 The demo
- Trigger: after P1.7
- Screen: the concept scene fades out and the console fades in. A legend ribbon draws across the top: teal Jev,
  violet Gemini, grey code, amber person.
- Thinking: none
- VO: To show this for real, I built a small IT service desk. Real Jev calls, real Gemini calls, real tools, over
  fake data. Everything you are about to see was recorded from a live run, and every number on screen was
  measured. Colour tells you who is thinking. Teal is Jev. Violet is Gemini. Grey is plain code. Amber is a person.

---

## Part 2. Watching it run

### Run A. The recipe request: Jev alone is enough

### A0 Slow motion
- Trigger: recording "recipe" restarts at 0.5x
- Screen: the console resets. The message is typed again. Spotlight dims everything except the graph.
- Thinking: none
- VO: First, the recipe request again, in slow motion.

### A1 Request received
- Trigger: node_start n-intake
- Screen: spotlight on the "Request received" node. Grey badge: "Fixed rule".
- Thinking: code
- VO: A message arrives. The first stop is plain code. It logs the request and checks who is asking. No AI
  here. {{intake_ms}} [twenty six milliseconds].

### A2 Input guardrails
- Trigger: node_start n-guard, then the guard card
- Screen: camera pushes in on the guardrail node. The Jev card opens with three yes or no rows. Each row's bar
  fills as it is named. The raw JSON toggle opens and the typed lines reveal one by one.
- Thinking: Jev
- VO: Now Jev. One call, three yes or no questions asked at the same time. Is this a prompt injection? Is it a
  jailbreak attempt? Is it unrelated to IT support? Back in {{guard_ms}} [about half a second]. The first two
  are low. The third says {{p_off}} percent [ninety seven].

### A3 Code decides
- Trigger: guard event with verdict "decline"
- Screen: a three-row truth table slides in from code. Row 1 "attack score at or above seventy: block" stays
  grey. Row 2 "unrelated at or above sixty: decline" lights amber and stamps.
- Thinking: code
- VO: Notice that Jev did not decide anything. A line of code did. Attack checks come first. Then, if
  unrelated is above sixty percent, decline. {{p_off}} percent is above sixty. Declined.

### A4 Decline
- Trigger: node_start n-block, then complete
- Screen: the Decline node lights, the reply appears addressed to Carol by name, the pills row slides in with
  "No model call", the Jev cost, and total time.
- Thinking: code
- VO: The reply is fixed text, addressed to Carol by name. No model was called. {{decline_total}} end to end,
  and the whole request cost {{decline_cost}} [under a hundredth of a cent].

### A5 The fair fight [X]
- Trigger: after A4. This is a recorded benchmark, never a live call
- Screen: split screen. Left, Jev. Right, Gemini Lite asked for structured output. Same three guardrail
  questions, same {{bench_n}} labelled test messages, replayed at recorded speed so the two bars race. Two counters
  tick: time and cost. Then two reliability charts side by side, "when it said ninety percent, how often was it
  right". A caption under both: "my messages, my prompts, measured here".
- Thinking: Jev and Gemini, side by side
- VO: Fair question: can't a language model do this with structured output? Yes, it can. Two things differ, speed
  and cost, and whether the confidence means anything. TypeSafe's numbers are their own, so I measured it myself.
  Same three questions, same {{bench_n}} test messages, Jev against Gemini Lite with structured output. Median
  time: {{bench_jev_ms}} for Jev, {{bench_gem_ms}} for Gemini. Cost for the whole set: {{bench_jev_cost}} against
  {{bench_gem_cost}}. On accuracy, {{bench_accuracy_phrase}}. And on honesty, {{bench_calibration_phrase}}.

### Run B. A real problem: locked out before a client call

### B0 Setup [X]
- Trigger: recording "locked out" starts at 1x
- Screen: the console resets. The identity chip shows Carol Wu, Finance. The message is typed.
- Thinking: none
- VO: Now a real problem. Carol is locked out of her account before a client call.

### B1 Opening checks
- Trigger: node_done n-guard
- Screen: the first two nodes tick off quickly. Camera stays wide.
- Thinking: code, then Jev
- VO: Same opening. Plain code first, then Jev checks for attacks. All three come back low.

### B2 Understand the request
- Trigger: understand card
- Screen: spotlight on "Understand request". Four yes or no rows and a "goes to" row. The row "Does it need
  investigation?" fills with a low bar and the words "No, {{p_inv}} percent sure".
- Thinking: Jev, then code
- VO: Next, Jev reads the request for meaning. The category is password, {{p_cat}} percent sure. Is work
  stopped? Yes. Does it need investigation? No, {{p_inv}} percent sure. These are small typed answers. Code
  turns them into a route, and the route says: send this to the resolution agent.

### B3 Plan the work
- Trigger: plan card
- Screen: spotlight on "Model and tools". Tool chips appear with scores, the unusable one is struck through.
  A three-position selector slides to "Lite".
- Thinking: Jev
- VO: Then Jev plans the work. Which tools could help, and which model size. It picks Gemini Lite,
  {{p_tier}} percent sure. The cheapest model that can do the job. Carol's permissions were already applied in
  code, so a tool she is not allowed to use does not exist for the model at all.

### B4 The agent starts [X]
- Trigger: node_start n-handle, then skill and tool_call events
- Screen: the violet Resolution agent node lights with its dots. Chat shows "Loaded skill account-access", the
  lookup, then `reset_password()` appearing. The colour on screen turns violet for the first time.
- Thinking: Gemini
- VO: Only now does a language model wake up. This is System Two. Gemini loads the account access skill, looks
  up Carol's account, sees that it is locked, and decides to call reset password.

### B5 The safety gate [X]
- Trigger: tool_call reset_password, then the safety event
- Screen: the Safety gate node lights beside the agent. The Jev safety card opens with three rows. Then a
  truth table appears and the row "account changes always need a person's approval" lights amber.
- Thinking: Jev, then code
- VO: But resetting a password changes something, so it has to pass the safety gate first. Jev answers three
  questions about the action. Does it raise anyone's access? {{p_priv}} percent. Is the requester verified?
  {{p_ver}} percent. Does it look like social engineering? {{p_atk}} percent. Then a table in code picks the
  outcome. The first row that matches says: account changes always need a person's approval.

### B6 A person decides [X]
- Trigger: gate waiting, then the recorded approval input
- Screen: the agent shows "paused" with no dots, the gate glows amber. The wait counter runs but is greyed out
  of the agent's budget. The identity chip animates from Carol to John with "Approving for Carol Wu". The
  approval card, the masked email, Approve is pressed, the chip animates back to Carol. A brief red flash: the
  recorded 403 when Carol tries to approve for herself.
- Thinking: person
- VO: So the agent pauses. The time spent waiting does not count against its budget. Only Carol's manager, John,
  can approve this, and nobody can approve their own request. I switch to John. Here is the action in plain
  words, with the email masked. Approve. And back to Carol. The server checks this too. If Carol tries to
  approve for herself, it answers four oh three.

### B7 The reply
- Trigger: tool_result, ttft, then complete
- Screen: the tool row turns green. The reply streams into the chat with a caret. A "first token" chip pops on
  the agent's header.
- Thinking: Gemini
- VO: The tool runs and Gemini writes the reply. It streams, and the first word arrives after {{ttft}}
  [about one second]. It opens with her first name, gives one clear next step, and uses no jargon, because that
  is what the style guide says for an employee.

### B8 Where the time went [X]
- Trigger: complete, pills, then the timeline
- Screen: the pills row slides in, then the run timeline draws bar by bar, each coloured by who was thinking.
  A stacked bar at the end: code, Jev, Gemini, waiting for a person.
- Thinking: all
- VO: Here is where the time went. {{n_jev}} Jev calls, {{jev_total_ms}} in all, costing {{jev_cost}}.
  {{n_gem}} Gemini calls, {{gem_total_ms}}, costing {{gem_cost}}. The model that wrote cost about {{ratio}}
  times what the model that judged cost, and that was the cheapest tier. Most of the rest was a person deciding.

### Run C. Someone tries a story

### C0 Setup
- Trigger: recording "social engineering" starts at 1x
- Screen: console resets, Carol again, the long message is typed.
- Thinking: none
- VO: One more. This time, someone tries a story.

### C1 Two layers
- Trigger: safety event with outcome "deny"
- Screen: the gate card shows the attack row at {{p_atk_c}} percent in red. The truth table's first row stamps
  "refuse". The agent is struck; no approval card appears. The reply says it cannot be done and gives the
  helpdesk number as the next step.
- Thinking: Jev, then code
- VO: Carol asks for Dan's password to be reset. The CEO needs his files, it is urgent. Two layers stop this.
  The first is code. The reset tool can only ever act on the person who is signed in, never on Dan. The second
  is Jev. At the gate it scores social engineering at {{p_atk_c}} percent. The first row of the table says, at
  seventy or above, refuse. Nobody was interrupted, and nothing ran.

### C2 The whole system [X]
- Trigger: after C1
- Screen: the graph zooms out and every node touched in the three runs stays lit in four colours, with counters
  for Jev calls, Gemini calls, approvals and refusals. Then seven tiles fly in, one per kind of job. Six light up
  as the camera replays the node that did it. The seventh stays dark.
- Thinking: all
- VO: That is the whole system. Jev judged {{total_jev_calls}} times across these runs. Gemini wrote. Code decided
  every outcome, and a person approved the one action that mattered. People use Jev for seven kinds of job: routing
  a request to a model, choosing a tool, checking whether a step is safe, business operations like support
  tickets, trust and safety, turning messy data into structure, and real time systems. This little desk used six
  of them. The seventh, real time, is where speed matters most, and a help desk does not need it.

---

## Part 3. The trade-offs

Screen for the whole part: the console steps back to a calm backdrop, one card per trade-off, each with a
real number or story from the recordings. No celebration, no music.

### T0 The honest part [X]
- VO: Now the honest part. This approach has costs.

### T1 It cannot write
- VO: One. Jev cannot write, explain, or act. TypeSafe say it plainly, Jev gives up generating text. So you
  still need a language model for the reply, and something to hold the conversation. Jev replaced the judging,
  not the thinking.

### T2 Hops add time
- Screen: the timeline replays with the three sequential Jev bars highlighted before the first Gemini bar.
- VO: Two. Hops add time. Three Jev calls ran one after another before Gemini even started, {{pre_llm_ms}} in
  total. I could run some of them in parallel, or merge them. I chose clarity. One direct language model call
  would start sooner, and it would be far harder to control.

### T3 Calibration is a statistic
- VO: Three. Calibration is a statistic. Ninety percent sure means wrong about one time in ten across many
  cases. It is not a guarantee about this one. I tuned some thresholds on thirty three test messages. That is a
  start, not evidence. A real system needs thousands, rechecked on every new model version.

### T4 The work moves [X]
- Screen: a card with the laptop screen ticket and "touches production: 53 to 74 percent", then the line
  "my code already knew", then the entry moving into `policy.toml`.
- VO: Four. The work moves, it does not vanish. You stop writing prompts and start designing questions and truth
  tables. I learned that the hard way. Jev rated a plain laptop screen ticket more than half likely to touch
  production. The fix was not a cleverer question. It was to stop asking, because my own code already knew.

### T5 Dependency and data
- VO: Five. Dependency and data. The state you send leaves your boundary, to one vendor's young model. TypeSafe's
  benchmark claims are theirs, and I used none of them. Every number in this video, I measured.

### T6 The people
- VO: And six, the people. A human approval step adds waiting, and the approver in this demo is a stand-in for
  real single sign on.

### T7 Close [X]
- Screen: three lines fade in one at a time over the quiet console. End card: lab title, the repo, a link to
  TypeSafe's docs, and the note "Narrated with an AI recreation of Gaurav's voice".
- VO: So here is how I think about it. Use System One where the answer is a judgment with a number. Use System
  Two where the answer is language. Put code between them, and keep a person in the loop where it matters.
  Thanks for watching.

---

## Slots: where each measured number comes from

| Slot | Source in the recording | Spoken as |
|---|---|---|
| decline_total | `complete.t` of the recipe run | "one point four seconds" |
| decline_cost | sum of `usage.cost_usd` in that run | "under a hundredth of a cent" |
| intake_ms, guard_ms | `node_done.ms` for n-intake, n-guard | "twenty six milliseconds", "about half a second" |
| p_off | `guard.data.scores.off_topic` | "ninety seven" |
| p_inj | `guard.data.scores.prompt_injection` | rounded to a whole percent |
| p_cat, p_inv | `understand.data.category.p`, `1 - effort.p` | whole percent |
| p_tier | `plan.data.tier_p` | whole percent |
| p_priv, p_ver, p_atk | `safety.scores.privileged`, `requester_verified`, `matches_attack_pattern` | whole percent, "no" reads as 100 minus |
| ttft | `ttft.ms` for n-handle | "about one second" |
| n_jev, n_gem | count of `usage` events by bucket s1 / s2 | "four", "three" |
| jev_total_ms, gem_total_ms | sum of step durations by mode | rounded to a friendly unit |
| jev_cost, gem_cost, ratio | sum of `usage.cost_usd` by bucket, then the ratio | "a fraction of a cent", "about twenty" |
| pre_llm_ms | `node_start` time of n-handle | "about one point two seconds" |
| jev_call_typical, jev_call_cost | median `node_done.ms` over Jev nodes, median `usage.cost_usd` per Jev call | words, not digits |
| p_atk_c | `safety.scores.matches_attack_pattern` in run C | whole percent |
| total_jev_calls | sum across the three runs | word |
| refund_p, team_top | a recorded live Jev call on the refund email: Noul `refund`, Choice `team` top option | whole percent, option name |
| bench_n | number of labelled messages in the recorded benchmark | a number |
| bench_jev_ms, bench_gem_ms | median call time per model over the benchmark | "about half a second", "about two seconds" |
| bench_jev_cost, bench_gem_cost | total cost over the benchmark per model | "a fraction of a cent" |
| bench_accuracy_phrase | picked from templates by the measured result: level, Gemini ahead by N points, or Jev ahead by N points | one clause |
| bench_calibration_phrase | picked from templates by the measured calibration gap on the same messages | one clause |

If a slot cannot be measured it is cut from the sentence, never estimated.

## Facts used from outside, and where they came from

| Statement in the script | Source |
|---|---|
| "Models have been superhuman at chat for years, so where is all the automation" is Diogo Almeida's driving question | TypeSafe launch post, "Introducing System One Models & Jev" |
| Launched September 2026 after two years in stealth | same post |
| He worked at OpenAI on the methods that made models follow instructions | same post, in his own words |
| Credited as co-inventor of RLHF | TypeSafe docs, AI primer |
| Name comes from Kahneman, "Thinking, Fast and Slow" | launch post FAQ and docs System One page |
| Jev is "the first System One model"; does not write replies, code, or explanations | docs, System One page |
| Calibration, RLCD, "outcomes assigned 0.2 should occur about 20 percent of the time" | docs primer and System One page |
| "An interface that software can depend on" | launch post closing line |
| Jev 1.14 available October 14, 2026 | docs, Models page |
| Jev named after William Stanley Jevons, tied to steam-engine efficiency raising demand; "every order of magnitude drop in the cost of intelligence unlocks orders of magnitude more use cases" | launch post FAQ. The phrase "Jevons paradox" does not appear there, so the script does not use it |
| RLHF optimises for human preference, RLVR for programmatically verifiable outputs, RLCD for calibrated decisions; LLMs sample sequentially, Jev in parallel | launch post comparison table |
| RLHF can teach a model to sound sure when wrong; RLVR only checks the final answer; pretraining then post training | Gaurav's study notes (IBM and CampusX videos), consistent with the TypeSafe home page on overconfidence |
| The seven kinds of job: model routing, tool selection, is this step safe, business operations, trust and safety, unstructured to structured, real time systems | Gaurav's study notes, not TypeSafe's page. TypeSafe's page lists four themes: workflows, big-data feature extraction, real-time apps, verification |
| The refund email and its three questions | Gaurav's study notes, the standard example in the talks. The numbers come from our own recorded Jev call |

Deliberately not used: TypeSafe's speed and cost multiples (for example "40x to 200x faster" and "193.6x faster,
444.6x cheaper"), the "about 100 ms" claim, the "70 ms to 500 ms" range, any benchmark or customer figure. Their
evals are self-run, and their post says so. They are company claims. Spec 96 says every number shown is measured from a recorded run.

## Draft length

| Part | Words (VO only) | Speaking time at 150 words a minute |
|---|---|---|
| Part 0. Cold open | 62 | 0.4 min |
| Part 1. Two ways to think | 736 | 4.9 min |
| Part 2. Watching it run | 817 | 5.4 min |
| Part 3. The trade-offs | 309 | 2.1 min |
| **Full tour** | **1924** | **12.8 min of speech** |
| **Express cut** (beats marked [X]) | **707** | **4.7 min of speech** |

Speech is only part of the runtime. Part 2 also plays the recorded runs, so the full tour lands near 14 to 15 minutes and the Express cut near 6. Idle waits in a recording, such as the approval pause, are compressed to a short beat. The full tour is long on purpose: it is the version you can scrub through by chapter. Express is the default.
