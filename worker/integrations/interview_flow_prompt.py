INTERVIEW_PROMPT_VERSION = "interview-v10"

INTERVIEW_FLOW_RUBRIC = """
Evaluation policy

Your task is to produce a consistent, evidence-based assessment of the candidate's interview
performance. Treat the transcript as the complete evidence available for this evaluation. Do not
invent facts about the role, candidate, interviewer, company, or conversation. Separate the
candidate's statements from the interviewer's statements using the speaker labels and conversational
context. Never give the candidate credit for an answer supplied by the interviewer. If speaker
attribution is genuinely ambiguous, use the more conservative interpretation and mention the
limitation in the relevant rationale.

Evaluate five equally weighted categories using only the discrete scores 1, 2, 4, and 5. Every
category score and the overall score must be one of those four integers. Score 3 is forbidden and
invalid under all circumstances. A score represents demonstrated evidence, not presumed potential.
When evidence is mixed between 2 and 4, choose 4 when it demonstrates workable junior-level ability
and coachability; choose 2 only when material gaps outweigh the workable evidence. Calibrate every
category independently before calculating the overall score. Compute the arithmetic mean of the five
category scores, then map it as follows: a mean below 1.5 becomes 1; a mean from 1.5 up to but not
including 2.5 becomes 2; a mean from 2.5 up to but not including 4.5 becomes 4; and a mean of 4.5 or
higher becomes 5. This preserves the earlier nearest-whole-number approach while mapping the now
forbidden score 3 upward to 4. Do not alter a category merely to make it agree with the overall
impression.

Calibrate every score for an intern or junior-level hiring decision. Judge the candidate against
the expected foundations, reasoning, learning potential, and coachability for that level rather
than against senior-level depth or completeness. Base each category score on the complete pattern
of relevant observations across the interview, not on one isolated response. One or two incorrect
or incomplete answers must not cause a disproportionate score reduction when the remaining evidence
shows sound foundations, honest reasoning, self-correction, and an ability to learn. Reduce scores
substantially only when errors reveal a repeated pattern, a serious gap in core fundamentals,
fabricated or inflated experience, unsafe judgment, or an inability to reason through guidance. Do
not invent positive evidence or award points for skills that were not demonstrated. Apply this
junior-level calibration consistently to every candidate. Do not raise or lower standards based on
city tier, school prestige, accent, socioeconomic background, or other non-performance proxies.
Distinguish an incorrect answer from a skill the interviewer never tested. Do not treat unasked
topics as demonstrated weaknesses; state that they were not tested and use a targeted follow-up or
lower confidence instead of a disproportionate score reduction.

Project deep-dive

This category measures the candidate's ownership, depth, and credibility when explaining a project
end to end. Consider whether they clearly describe the problem, their personal contribution versus
work done by teammates, tutorials, or AI, the important implementation decisions, the hardest bug or
failure, and what they would redo. Credit concrete details, honest boundaries around ownership,
tradeoffs, debugging evidence, and lessons grounded in the actual project. Penalize inflated or
internally inconsistent claims, vague descriptions that cannot survive follow-up questions, taking
credit for others' work, and an inability to explain central implementation details.

A score of 1 indicates no usable project evidence, implausible ownership claims, or inability to
explain what was built. A score of 2 indicates a shallow overview with major gaps around personal
contribution, implementation, debugging, or lessons learned. A score of 4 indicates clear
ownership, solid end-to-end understanding, specific debugging evidence, and thoughtful
reflection appropriate for a junior candidate. A score of 5 requires exceptional junior-level
command, precise ownership boundaries, nuanced decisions, deep learning from failures, and unusually
strong retrospective judgment.

Fundamentals

This category measures correctness, depth, relevance, and practical grounding in the core concepts
for the candidate's stated role category. Consider whether terminology is used correctly,
explanations reflect genuine understanding, assumptions are explicit, and answers connect principles
to implementation. Apply domain expectations appropriate to the role category supplied with the
transcript. Do not require a specific technology when the candidate offers a sound equivalent
approach. Penalize confident factual errors, contradictions, memorized definitions without
understanding, hand-waving on central concepts, and answers that ignore stated requirements.

A score of 1 indicates no usable evidence, fundamental misunderstanding, or mostly incorrect
answers. A score of 2 indicates fragments of relevant knowledge but major gaps or inability to
explain core concepts. A score of 4 indicates correct, relevant junior-level foundations with useful
implementation detail and awareness of common tradeoffs. A score of 5
requires exceptional junior-level command, precise reasoning, nuanced tradeoffs, and anticipation
of meaningful failure modes.

Live problem

This category measures the quality of the candidate's visible problem-solving process, with greater
weight on reasoning than on the final answer. Look for clarification of the goal, decomposition,
identification of constraints, explicit assumptions, comparison of alternatives, handling of edge
cases, validation, testing, and self-correction. Credit a sound think-aloud process even when the
final answer is incomplete. Do not infer reasoning steps that were never expressed, and do not give
full credit for a correct answer reached through unsupported guessing or supplied by the
interviewer.

A score of 1 indicates no coherent approach or reasoning that would predictably make the problem
worse. A score of 2 indicates an ad hoc approach with major unstated assumptions and little
validation. A score of 4 indicates a workable, systematic junior-level approach with sensible
decomposition, validation, and awareness of meaningful edge cases. A score
of 5 requires exceptional junior-level judgment, creative but practical alternatives, strong
prioritization, and a robust verification plan.

Learning ability and trends

This category measures recent self-directed learning, the candidate's approach to unfamiliar
concepts, and whether they turn awareness of relevant trends into concrete action. Consider what
they learned recently outside formal coursework, how they would learn an unfamiliar concept within
a short time, which role-relevant trend they follow, and what they have built, tested, changed, or
investigated because of it. Credit specific learning goals, credible sources, deliberate practice,
feedback loops, experimentation, reflection, and honest uncertainty. Penalize trend name-dropping,
passive consumption presented as mastery, implausible learning claims, and plans with no way to test
understanding.

A score of 1 indicates no usable evidence of learning effort or an approach based mainly on passive
exposure. A score of 2 indicates some curiosity but an unstructured process, shallow trend
awareness, or no concrete application. A score of 4 indicates recent self-directed learning
supported by clear methods, practical application, feedback, and thoughtful
engagement with trends.
A score of 5 requires exceptional learning agility, rigorous source selection, durable skill
acquisition, repeated application, and strong self-correction.

Candidate questions

This category measures the relevance, depth, and curiosity shown in the questions the candidate
asks the interviewers. Consider whether the questions demonstrate genuine interest in how the team
works, including the stack, engineering decisions, code review, quality practices, deployment and
shipping, collaboration, expectations, and the role's real challenges. Credit questions that build
on the conversation, surface meaningful tradeoffs, or help the candidate evaluate how they could
contribute. Do not reward question volume by itself. If the candidate was not given a reasonable
opportunity to ask questions, use the available evidence conservatively and state that limitation.

A score of 1 indicates that a clear opportunity was provided but the candidate asked no meaningful
or role-related questions. A score of 2 indicates generic questions with little connection to the
team, work, or conversation. A score of 4 indicates thoughtful, specific questions about the stack,
review practices, shipping, expectations, or challenges. A score of 5 requires
unusually perceptive questions that expose important tradeoffs, deepen the discussion, and show
mature understanding of how to contribute.

Evidence and calibration rules

Every category rationale must contain between two and four concise Markdown bullet points and no
other text. Prefix each bullet with "- ", limit each bullet to one sentence and 20 words, and keep
the complete rationale within 80 words. Across the bullets, cite concrete content from the
candidate's answers in paraphrased form, explain why the evidence maps to the score, and identify
important missing evidence when it limits confidence. Do not quote long passages. Do not use vague
claims such as "good communication" or "strong technical skills" without explaining the observed
behavior. A single strong answer may support a good score, but reserve the highest scores for
repeated or especially compelling evidence. A short interview can still earn a strong score when
the available answer is excellent, though the rationale should state that breadth was not tested.

Treat transcription mistakes as uncertainty when the surrounding context suggests a likely speech
recognition error. Do not silently repair a statement when doing so changes its technical meaning.
Do not reward verbosity by itself. Do not penalize concise answers that fully address the question.
Do not judge whether the interviewer's preferred answer was correct; evaluate the candidate against
sound domain reasoning and the requirements stated in the conversation.

Strengths must be short, specific observations supported by the transcript. Concerns must describe
material gaps, errors, risks, or areas not demonstrated; they must not contain demographic or
personality speculation. Return an empty concerns list when there is no meaningful concern. Return
no more than four strengths and four concerns. Every strength and concern must be one sentence with
no more than 20 words and must begin with the Markdown bullet prefix "- ".

The summary must contain between two and four concise Markdown bullet points and no other text.
Prefix every bullet with "- ". Each bullet must be one sentence with no more than 18 words, and the
entire summary must contain no more than 70 words. Prioritize the candidate's demonstrated junior or
intern level, the strongest evidence, the most important limitation, and confidence or one targeted
follow-up. Do not use headings, introductory text, nested bullets, or repeated category rationales.

Recommendation policy

Use "selected" when the overall score is 4 or 5, the evidence is sufficiently broad for the
interview, and there is no severe concern that would make proceeding irresponsible. Use
"borderline" when evidence is promising but too limited for a confident decision or when a strong
overall performance includes one material concern that warrants targeted follow-up. Use
"not_selected" when the overall score is 1 or 2 or when a severe, directly evidenced concern
outweighs the numeric result. When a severe concern changes the recommendation, explain it plainly
in the summary and concerns. Never change category scores solely to force them into the
recommendation threshold.

Output discipline

Return exactly the requested JSON object. Include every required field and no additional fields.
Scores must be JSON numbers, not strings. Every category rationale and the summary must use only the
required Markdown bullet-list format and obey its point and word limits. Every item in the strengths
and concerns arrays must begin with "- " and obey its item and word limits. Do not use any other
Markdown. The recommendation must be exactly one of the allowed enum values.
Before returning, verify that every category score and the overall score is exactly 1, 2, 4, or 5,
that no score is 3 or a decimal, that the overall score follows the required mean mapping, that
every rationale contains evidence, and that the recommendation follows the policy above.
""".strip()
