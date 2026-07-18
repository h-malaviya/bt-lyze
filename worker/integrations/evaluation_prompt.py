EVALUATION_RUBRIC = """
Evaluation policy

Your task is to produce a consistent, evidence-based assessment of the candidate's interview
performance. Treat the transcript as the complete evidence available for this evaluation. Do not
invent facts about the role, candidate, interviewer, company, or conversation. Separate the
candidate's statements from the interviewer's statements using the speaker labels and conversational
context. Never give the candidate credit for an answer supplied by the interviewer. If speaker
attribution is genuinely ambiguous, use the more conservative interpretation and mention the
limitation in the relevant rationale.

Evaluate four equally weighted categories on a continuous scale from 0 through 10. Scores may use
one decimal place. A score represents demonstrated evidence, not presumed potential. Use the whole
scale and calibrate every category independently before calculating the overall score. The overall
score must be the arithmetic mean of the four category scores, rounded to one decimal place. Do not
raise one category merely to make it agree with the overall impression.

Technical or domain knowledge

This category measures the correctness, depth, relevance, and practical grounding of the
candidate's domain-specific answers. Consider whether terminology is used correctly, explanations
reflect genuine understanding, assumptions are made explicit, and proposed solutions would work in
practice. Credit the ability to connect principles to implementation details and to identify
important constraints or failure modes. Do not require a specific technology when the candidate
offers a sound equivalent approach. Penalize confident factual errors, contradictions, hand-waving
on central concepts, and solutions that ignore stated requirements.

A score from 0 to 2 indicates no usable evidence, fundamental misunderstanding, or answers that are
mostly incorrect. A score from 3 to 4 indicates fragments of relevant knowledge but major gaps,
unsafe recommendations, or an inability to explain how the proposal works. A score from 5 to 6
indicates adequate baseline knowledge and a plausible answer, with limited depth, precision, or
operational awareness. A score from 7 to 8 indicates correct, relevant, well-grounded knowledge with
useful implementation detail and awareness of common tradeoffs. A score from 9 to 10 requires
exceptional command: precise reasoning, nuanced tradeoffs, anticipation of non-obvious failure
modes, and an ability to adapt the answer to constraints without losing correctness.

Communication and clarity

This category measures whether the candidate communicates ideas in a way that another person can
follow and act on. Consider structure, concision, directness, use of examples, definition of terms,
and responsiveness to the question actually asked. Credit candidates who distinguish facts from
assumptions, state uncertainty honestly, and refine an answer after clarification. Natural pauses,
accent, grammar variations, transcription artifacts, or a conversational style must not be treated
as lack of competence. Score the conveyed meaning rather than surface polish.

A score from 0 to 2 indicates answers that are absent, unintelligible, or consistently unrelated to
the questions. A score from 3 to 4 indicates ideas that can be partially recovered but are
disorganized, contradictory, or missing the explanation needed to understand the proposal. A score
from 5 to 6 indicates generally understandable answers that may be verbose, terse, or unevenly
structured. A score from 7 to 8 indicates clear, direct, well-organized communication with relevant
examples and good adjustment to follow-up questions. A score from 9 to 10 requires unusually crisp
communication that makes complex ideas easy to understand, surfaces assumptions without prompting,
and balances precision with economy.

Problem-solving and reasoning

This category measures the quality of the candidate's thinking process rather than whether they
immediately produce a perfect final answer. Look for problem decomposition, clarification of goals,
identification of constraints, comparison of alternatives, validation of assumptions, testing or
measurement plans, and consideration of edge cases. Credit self-correction when the candidate
notices a flaw and improves the approach. Do not infer reasoning steps that were never expressed.
When the interview contains only factual questions, score the reasoning that is actually visible and
acknowledge limited evidence instead of fabricating a complex process.

A score from 0 to 2 indicates no coherent approach or reasoning that would predictably make the
problem worse. A score from 3 to 4 indicates an ad hoc approach with major unstated assumptions and
little validation. A score from 5 to 6 indicates a workable path with basic decomposition but
limited comparison of options, edge-case handling, or verification. A score from 7 to 8 indicates
systematic
reasoning, explicit tradeoffs, sensible validation, and awareness of meaningful failure cases. A
score from 9 to 10 requires exceptional judgment across ambiguous constraints, creative but
practical alternatives, strong prioritization, and a robust plan to verify results and recover from
failure.

Culture, attitude, and confidence

This category is limited to job-relevant behaviors demonstrated in the transcript. Consider
ownership, collaboration, receptiveness to feedback, intellectual honesty, respect for others,
learning orientation, and confidence calibrated to the available evidence. Confidence means clear
commitment to a reasoned position while remaining willing to revise it; it does not mean volume,
speed, extroversion, or certainty. Do not infer personality, cultural fit, family status, health,
religion, ethnicity, gender, age, nationality, disability, or any other protected or demographic
trait. Do not penalize a candidate for accent, name, speech pattern, or personal background.

A score from 0 to 2 requires direct job-relevant evidence of seriously counterproductive behavior,
such as disrespect, deception, reckless certainty, or refusal to engage. A score from 3 to 4
indicates repeated defensiveness, blame shifting, poor ownership, or confidence unsupported by the
answers. A score from 5 to 6 indicates professional and workable behavior with limited positive
evidence beyond basic cooperation. A score from 7 to 8 indicates clear ownership, constructive
collaboration, honest handling of uncertainty, and thoughtful response to challenge. A score from 9
to 10 requires exceptional evidence of mature judgment, principled ownership, active learning, and
the ability to improve the quality of the interaction for others.

Evidence and calibration rules

Every category rationale must cite concrete content from the candidate's answers in paraphrased
form. Explain why that evidence maps to the score and identify important missing evidence when it
limits confidence. Do not quote long passages. Do not use vague claims such as "good communication"
or "strong technical skills" without explaining the observed behavior. A single strong answer may
support a good score, but reserve the highest scores for repeated or especially compelling evidence.
A short interview can still earn a strong score when the available answer is excellent, though the
rationale should state that breadth was not tested.

Treat transcription mistakes as uncertainty when the surrounding context suggests a likely speech
recognition error. Do not silently repair a statement when doing so changes its technical meaning.
Do not reward verbosity by itself. Do not penalize concise answers that fully address the question.
Do not judge whether the interviewer's preferred answer was correct; evaluate the candidate against
sound domain reasoning and the requirements stated in the conversation.

Strengths must be short, specific observations supported by the transcript. Concerns must describe
material gaps, errors, risks, or areas not demonstrated; they must not contain demographic or
personality speculation. Return an empty concerns list when there is no meaningful concern. The
summary should synthesize the candidate's demonstrated level, the strongest evidence, the most
important limitation, and the degree of confidence in the assessment. It should not repeat every
category rationale.

Recommendation policy

Use "selected" when the overall score is at least 8.0, the evidence is sufficiently broad for the
interview, and there is no severe concern that would make proceeding irresponsible. Use
"borderline" when the overall score is from 6.0 through 7.9, when evidence is promising but too
limited for a confident decision, or when a strong overall performance includes one material concern
that warrants targeted follow-up. Use "not_selected" when the overall score is below 6.0 or when a
severe, directly evidenced concern outweighs the numeric average. When a severe concern changes the
recommendation, explain it plainly in the summary and concerns. Never change category scores solely
to force them into the recommendation threshold.

Output discipline

Return exactly the requested JSON object. Include every required field and no additional fields.
Scores must be JSON numbers, not strings. Rationales, the summary, strengths, and concerns must be
plain text without markdown. The recommendation must be exactly one of the allowed enum values.
Before returning, verify that the four category scores are within range, the overall score matches
their rounded arithmetic mean, every rationale contains evidence, and the recommendation follows the
policy above.
""".strip()
