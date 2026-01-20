Tuesday 20 June 2023 – Afternoon
A Level Mathematics B (MEI)
H640/03 Pure Mathematics and Comprehension
Time allowed: 2 hours

You must have:
• the Printed Answer Booklet
• the Insert
• a scientific or graphical calculator

INSTRUCTIONS
• Use black ink. You can use an HB pencil, but only for graphs and diagrams.
• Write your answer to each question in the space provided in the Printed Answer Booklet. If you need extra space use the lined pages at the end of the Printed Answer Booklet. The question numbers must be clearly shown.
• Fill in the boxes on the front of the Printed Answer Booklet.
• Answer all the questions.
• Where appropriate, your answer should be supported with working. Marks might be given for using a correct method, even if your answer is wrong.
• Give your final answers to a degree of accuracy that is appropriate to the context.
• Do not send this Question Paper for marking. Keep it in the centre or recycle it.

INFORMATION
• The total mark for this paper is 75.
• The marks for each question are shown in brackets [ ].
• This document has 12 pages.

ADVICE
• Read each question carefully before you start your answer.
Formulae A Level Mathematics B (MEI) (H640)

Arithmetic series

\[
S_n = \frac{1}{2}n(a+l) = \frac{1}{2}n\{2a + (n-1)d\}
\]

Geometric series

\[
S_n = \frac{a(1-r^n)}{1-r}
\]
\[
S_\infty = \frac{a}{1-r} \quad \text{for } |r| < 1
\]

Binomial series

\[
(a+b)^n = a^n + {}^nC_1 a^{n-1} b + {}^nC_2 a^{n-2} b^2 + \ldots + {}^nC_r a^{n-r} b^r + \ldots + b^n \qquad (n \in \mathbb{N}),
\]
where \( {}^nC_r = {}_n C_r = \binom{n}{r} = \frac{n!}{r!(n-r)!} \)

\[
(1+x)^n = 1 + nx + \frac{n(n-1)}{2!} x^2 + \ldots + \frac{n(n-1)\ldots(n-r+1)}{r!} x^r + \ldots \qquad (|x| < 1, \ n \in \mathbb{R})
\]

Differentiation

<table>
  <tr>
    <th>f(x)</th>
    <th>f'(x)</th>
  </tr>
  <tr>
    <td>\( \tan kx \)</td>
    <td>\( k \sec^2 kx \)</td>
  </tr>
  <tr>
    <td>\( \sec x \)</td>
    <td>\( \sec x \tan x \)</td>
  </tr>
  <tr>
    <td>\( \cot x \)</td>
    <td>\( -\cosec^2 x \)</td>
  </tr>
  <tr>
    <td>\( \cosec x \)</td>
    <td>\( -\cosec x \cot x \)</td>
  </tr>
</table>

Quotient Rule \( y = \frac{u}{v}, \ \frac{dy}{dx} = \frac{\frac{du}{dx} - \frac{dv}{dx}}{v^2} \)

Differentiation from first principles

\[
f'(x) = \lim_{h \to 0} \frac{f(x+h) - f(x)}{h}
\]

Integration

\[
\int \frac{f'(x)}{f(x)} \, dx = \ln|f(x)| + c
\]
\[
\int f'(x)(f(x))^n \, dx = \frac{1}{n+1}(f(x))^{n+1} + c
\]

Integration by parts \( \int u \frac{dv}{dx} \, dx = uv - \int v \frac{du}{dx} \, dx \)

Small angle approximations

\[
\sin \theta \approx \theta, \ \cos \theta \approx 1 - \frac{1}{2}\theta^2, \ \tan \theta \approx \theta \quad \text{where } \theta \text{ is measured in radians}
\]
Trigonometric identities
\[
\sin(A \pm B) = \sin A \cos B \pm \cos A \sin B \\
\cos(A \pm B) = \cos A \cos B \mp \sin A \sin B \\
\tan(A \pm B) = \frac{\tan A \pm \tan B}{1 \mp \tan A \tan B} \quad (A \pm B \neq (k + \frac{1}{2})\pi)
\]

Numerical methods
Trapezium rule: \( \int_a^b y \, dx \approx \frac{1}{2}h\{(y_0 + y_n) + 2(y_1 + y_2 + \ldots + y_{n-1})\} \), where \( h = \frac{b-a}{n} \)

The Newton-Raphson iteration for solving f(x) = 0: \( x_{n+1} = x_n - \frac{f(x_n)}{f'(x_n)} \)

Probability
\[
P(A \cup B) = P(A) + P(B) - P(A \cap B) \\
P(A \cap B) = P(A)P(B|A) = P(B)P(A|B) \quad \text{or} \quad P(A|B) = \frac{P(A \cap B)}{P(B)}
\]

Sample variance
\[
s^2 = \frac{1}{n-1} S_{xx} \text{ where } S_{xx} = \sum (x_i - \bar{x})^2 = \sum x_i^2 - \frac{(\sum x_i)^2}{n} = \sum x_i^2 - n\bar{x}^2
\]
Standard deviation, \( s = \sqrt{\text{variance}} \)

The binomial distribution
If \( X \sim \mathrm{B}(n, p) \) then \( P(X = r) = {}^nC_r p^r q^{n-r} \) where \( q = 1 - p \)
Mean of \( X \) is \( np \)

Hypothesis testing for the mean of a Normal distribution
If \( X \sim \mathrm{N}(\mu, \sigma^2) \) then \( \overline{X} \sim \mathrm{N}\left( \mu, \frac{\sigma^2}{n} \right) \) and \( \frac{\overline{X} - \mu}{\sigma/\sqrt{n}} \sim \mathrm{N}(0, 1) \)

Percentage points of the Normal distribution

<table>
  <tr>
    <th>p</th>
    <th>10</th>
    <th>5</th>
    <th>2</th>
    <th>1</th>
  </tr>
  <tr>
    <th>z</th>
    <td>1.645</td>
    <td>1.960</td>
    <td>2.326</td>
    <td>2.576</td>
  </tr>
</table>

Kinematics
Motion in a straight line
\[
v = u + at \\
s = ut + \frac{1}{2}at^2 \\
s = \frac{1}{2}(u+v)t \\
v^2 = u^2 + 2as \\
s = vt - \frac{1}{2}at^2
\]

Motion in two dimensions
\[
v = \mathbf{u} + \mathbf{a}t \\
s = \mathbf{u}t + \frac{1}{2}\mathbf{a}t^2 \\
s = \frac{1}{2}(\mathbf{u}+\mathbf{v})t \\
s = \mathbf{v}t - \frac{1}{2}\mathbf{a}t^2
\]
Section A (60 marks)

1  In this question you must show detailed reasoning.

The obtuse angle \( \theta \) is such that \( \sin \theta = \frac{2}{\sqrt{13}} \).

Find the exact value of \( \cos \theta \). [3]

2  The straight line \( y = 5 - 2x \) is shown in the diagram.

![A coordinate axis with a dashed line passing through the origin and having a negative slope, labeled y and x.](page_349_484_370_370.png)

(a) On the copy of the diagram in the Printed Answer Booklet, sketch the graph of \( y = |5 - 2x| \). [1]

(b) Solve the inequality \( |5 - 2x| < 3 \). [3]

3  In this question you must show detailed reasoning.

Find the value of \( k \) such that \( \frac{1}{\sqrt{5} + \sqrt{6}} + \frac{1}{\sqrt{6} + \sqrt{7}} = \frac{k}{\sqrt{5} + \sqrt{7}} \). [3]
4 In this question you must show detailed reasoning.

Find the coordinates of the points where the curve \( y = x^3 - 2x^2 - 5x + 6 \) crosses the x-axis. [4]

5 In this question you must show detailed reasoning.

This question is about the curve \( y = x^3 - 5x^2 + 6x \).

(a) Find the equation of the tangent, \( T \), to the curve at the point (0, 0). [3]

(b) Find the equation of the normal, \( N \), to the curve at the point (1, 2). [3]

(c) Find the coordinates of the point of intersection of \( T \) and \( N \). [2]
6 (a) Quadrilateral KLMN has vertices K (−4, 1), L (5, −1), M (6, 2) and N (2, 5), as shown in Fig. 6.1.

Fig. 6.1

![Quadrilateral KLMN with vertices labeled and midpoints P, Q, R, S](page_370_180_693_377.png)

(i) Find the coordinates of the following midpoints.
    • P, the midpoint of KL
    • Q, the midpoint of LM
    • R, the midpoint of MN
    • S, the midpoint of NK [2]

(ii) Verify that PQRS is a parallelogram. [3]

(b) TVWX is a quadrilateral as shown in Fig. 6.2.

Points A and B divide side TV into 3 equal parts. Points C and D divide side VW into 3 equal parts. Points E and F divide side WX into 3 equal parts. Points G and H divide side TX into 3 equal parts.

\( \overrightarrow{TA} = \mathbf{a}, \quad \overrightarrow{TH} = \mathbf{b}, \quad \overrightarrow{VC} = \mathbf{c}. \)

Fig. 6.2

![Quadrilateral TVWX with points A, B, C, D, E, F, G, H labeled and vectors a, b, c](page_370_1012_693_377.png)

(i) Show that \( \overrightarrow{WX} = k(-\mathbf{a} + \mathbf{b} - \mathbf{c}) \), where \( k \) is a constant to be determined. [1]

(ii) Verify that AH is parallel to DE. [2]

(iii) Verify that BC is parallel to GF. [2]
7  A wire, 10 cm long, is bent to form the perimeter of a sector of a circle, as shown in the diagram. The radius is \( r \) cm and the angle at the centre is \( \theta \) radians.

![Diagram of a sector of a circle with radius r and angle theta](page_184_120_246_180.png)

Determine the maximum possible area of the sector, showing that it is a maximum. [6]

8  A circle with centre A and radius 8 cm and a circle with centre C and radius 12 cm intersect at points B and D.

Quadrilateral ABCD has area 60 cm\(^2\).

Determine the two possible values for the length AC. [7]
9 A small country started using solar panels to produce electrical energy in the year 2000. Electricity production is measured in megawatt hours (MWh).

For the period from 2000 to 2009, the annual electrical energy produced using solar panels can be modelled by the equation \( P = 0.3e^{0.5t} \), where \( P \) is the annual amount of electricity produced in MWh and \( t \) is the time in years after the year 2000.

(a) According to this model, find the amount of electricity produced using solar panels in each of the following years.

(i) 2000 [1]

(ii) 2009 [1]

(b) Give a reason why the model is unlikely to be suitable for predicting the annual amount of electricity produced using solar panels in the year 2025. [1]

An alternative model is suggested; the curve representing this model is shown in Fig. 9.

Fig. 9

![A graph showing the alternative model for annual electricity production over time, with axes labeled P (vertical) and t (horizontal)](page_420_670_1008_410.png)

(c) Explain how the graph shows that the alternative model gives a value for the amount of electricity produced in 2009 that is consistent with the original model. [1]

(d) (i) On the axes given in the Printed Answer Booklet, sketch the gradient function of the model shown in Fig. 9. [2]

(ii) State approximately the value of \( t \) at the point of inflection in Fig. 9. [1]

(iii) Interpret the significance of the point of inflection in the context of the model. [1]

(e) State approximately the long term value of the annual amount of electricity produced using solar panels according to the model represented in Fig. 9. [1]
10 (a) You are given that \( (x^2 + y^2)^3 = x^6 + 3x^4y^2 + 3x^2y^4 + y^6 \).

Hence, or otherwise, prove that \( \sin^6 \theta + \cos^6 \theta = 1 - \frac{3}{4} \sin^2 2\theta \) for all values of \( \theta \). [4]

(b) Use the result from part (a) to determine the minimum value of \( \sin^6 \theta + \cos^6 \theta \). [2]
Section B (15 marks)

The questions in this section refer to the article on the Insert. You should read the article before attempting the questions.

11 (a) Evaluate \( \sum_{r=1}^{5} r^2 \). [1]

(b) Show that Euler’s approximate formula, as given in line 13, gives the exact value of \( \sum_{r=1}^{5} r^2 \). [2]

12 With the aid of a suitable diagram, show that the three triangles referred to in line 26 have the areas given in line 27. [3]

13 Prove that Euler’s approximate formula, as given in line 13, when applied to \( \sum_{r=1}^{n} r^2 \) gives exactly \( \frac{n(n+1)(2n+1)}{6} \). [4]

14 Show that the expression given in line 33 simplifies to \( \sum_{r=1}^{n} \frac{1}{r} \approx \ln n + \frac{13}{24} + \frac{6n+5}{12n(n+1)} \), as given in line 34. [3]

15 The expression given in line 34 is used to calculate \( \sum_{r=1}^{6} \frac{1}{r} \).
Show that the error in the result is less than 1.5% of the true value. [2]
BLANK PAGE
OCR
Oxford Cambridge and RSA

Copyright Information
OCR is committed to seeking permission to reproduce all third-party content that it uses in its assessment materials. OCR has attempted to identify and contact all copyright holders whose work is used in this paper. To avoid the issue of disclosure of answer-related information to candidates, all copyright acknowledgements are reproduced in the OCR Copyright Acknowledgements Booklet. This is produced for each series of examinations and is freely available to download from our public website (www.ocr.org.uk) after the live examination series.
If OCR has unwittingly failed to correctly acknowledge or clear any third-party content in this assessment material, OCR will be happy to correct its mistake at the earliest possible opportunity.
For queries or further information please contact The OCR Copyright Team, The Triangle Building, Shaftesbury Road, Cambridge CB2 8EA.
OCR is part of Cambridge University Press & Assessment, which is itself a department of the University of Cambridge.