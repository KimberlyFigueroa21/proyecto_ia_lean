# Auditoría del conjunto de evaluación

Marca cada casilla con `x`. Dos preguntas por problema:

- **Área**: ¿la etiqueta (álgebra, teoría de números, conteo) es razonable? Las de `heurística` se asignaron por palabras clave y son las más dudosas.
- **Fidelidad** (solo los marcados con ★): ¿el enunciado en Lean significa lo mismo que el enunciado en lenguaje natural? Si no, es una mala formalización: anótala en Observaciones.

## imo_1962_p2

- Split: **dev** · Dificultad: avanzado · Área: algebra (`heuristica`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> Determine all real numbers $x$ which satisfy the inequality: \[ \sqrt{3-x}-\sqrt{x+1}>\dfrac{1}{2} \]

Lean:

```lean
theorem imo_1962_p2 :
    {x : ℝ | 0 ≤ 3 - x ∧ 0 ≤ x + 1 ∧ 1 / 2 < Real.sqrt (3 - x) - Real.sqrt (x + 1)} =
      Set.Ico (-1) (1 - Real.sqrt 31 / 8)
```

## mathd_algebra_141

- Split: **dev** · Dificultad: basico · Área: algebra (`nombre`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> A rectangular patio has an area of $180$ square feet and a perimeter of $54$ feet. What is the length of the diagonal (in feet) squared?

Lean:

```lean
theorem mathd_algebra_141 (a b : ℝ) (h₁ : a * b = 180) (h₂ : 2 * (a + b) = 54) :
    a ^ 2 + b ^ 2 = 369
```

## mathd_algebra_33

- Split: **dev** · Dificultad: basico · Área: algebra (`nombre`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> If $2x = 5y$ and $7y = 10z$, what is the value of $\frac{z}{x}$ expressed as a common fraction?

Lean:

```lean
theorem mathd_algebra_33 (x y z : ℝ) (h₀ : x ≠ 0) (h₁ : 2 * x = 5 * y) (h₂ : 7 * y = 10 * z) :
    z / x = 7 / 25
```

## mathd_algebra_398 ★ FIDELIDAD

- Split: **dev** · Dificultad: basico · Área: algebra (`nombre`)
- [ ] Área correcta   - [ ] Fidelidad correcta
- Observaciones: 

Lenguaje natural:

> On planet Larky, 7 ligs = 4 lags, and 9 lags = 20 lugs. How many ligs are equivalent to 80 lugs?

Lean:

```lean
theorem mathd_algebra_398 (a b c : ℝ) (h₀ : 0 < a ∧ 0 < b ∧ 0 < c) (h₁ : 9 * b = 20 * c)
    (h₂ : 7 * a = 4 * b) : 63 * a = 80 * c
```

## amc12_2000_p20

- Split: **dev** · Dificultad: intermedio · Área: algebra (`heuristica`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> If $ x$, $ y$, and $ z$ are positive numbers satisfying \[x +{} 1/y ={} 4,\quad y +{} 1/z ={} 1,\quad\text{and}\quad z +{} 1/x ={} 7/3,\] then $ xyz ={}$ $ \textbf{(A)}\ 2/3 \qquad \textbf{(B)}\ 1 \qquad \textbf{(C)}\ 4/3 \qquad \textbf{(D)}\ 2 \qquad \textbf{(E)}\ 7/3$

Lean:

```lean
theorem amc12_2000_p20 (x y z : ℝ) (h₀ : 0 < x ∧ 0 < y ∧ 0 < z) (h₁ : x + 1 / y = 4)
    (h₂ : y + 1 / z = 1) (h₃ : z + 1 / x = 7 / 3) : x * y * z = 1
```

## mathd_numbertheory_12

- Split: **dev** · Dificultad: basico · Área: conteo (`enunciado`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> How many integers between 15 and 85 are divisible by 20?

Lean:

```lean
theorem mathd_numbertheory_12 :
    Finset.card (Finset.filter (fun x => 20 ∣ x) (Finset.Icc 15 85)) = 4
```

## amc12a_2021_p19

- Split: **dev** · Dificultad: intermedio · Área: conteo (`enunciado`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> How many solutions does the equation $\sin \left( \frac{\pi}2 \cos x\right)=\cos \left( \frac{\pi}2 \sin x\right)$ have in the closed interval $[0,\pi]$? $\textbf{(A) }0 \qquad \textbf{(B) }1 \qquad \textbf{(C) }2 \qquad \textbf{(D) }3\qquad \textbf{(E) }4$

Lean:

```lean
theorem amc12a_2021_p19 (S : Finset ℝ)
    (h₀ :
      ∀ x : ℝ,
        x ∈ S ↔
          0 ≤ x ∧
            x ≤ Real.pi ∧
              Real.sin (Real.pi / 2 * Real.cos x) = Real.cos (Real.pi / 2 * Real.sin x)) :
    S.card = 2
```

## imo_1974_p3

- Split: **dev** · Dificultad: avanzado · Área: teoria_de_numeros (`heuristica`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> Prove that for any n natural, the number \[ \sum \limits_{k=0}^{n} \binom{2n+1}{2k+1} 2^{3k} \] cannot be divided by $5$.

Lean:

```lean
theorem imo_1974_p3 (n : ℕ) :
    ¬5 ∣ ∑ k ∈ Finset.range (n + 1), Nat.choose (2 * n + 1) (2 * k + 1) * 2 ^ (3 * k)
```

## mathd_numbertheory_521

- Split: **dev** · Dificultad: basico · Área: teoria_de_numeros (`nombre`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> The product of two consecutive positive even integers is 288. What is the greater of the two integers?

Lean:

```lean
theorem mathd_numbertheory_521 (m n : ℕ) (h₀ : Even m) (h₁ : Even n) (h₂ : m - n = 2)
    (h₃ : m * n = 288) : m = 18
```

## mathd_numbertheory_99

- Split: **dev** · Dificultad: basico · Área: teoria_de_numeros (`nombre`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> Solve the congruence $2n \equiv 15 \pmod{47}$, as a residue modulo 47. (Give an answer between 0 and 46.)

Lean:

```lean
theorem mathd_numbertheory_99 (n : ℕ) (h₀ : 2 * n % 47 = 15) : n % 47 = 31
```

## aime_1983_p3 ★ FIDELIDAD

- Split: **test** · Dificultad: avanzado · Área: algebra (`heuristica`)
- [ ] Área correcta   - [ ] Fidelidad correcta
- Observaciones: 

Lenguaje natural:

> What is the product of the real roots of the equation \[x^2 + 18x + 30 = 2 \sqrt{x^2 + 18x + 45}\,\,?\]

Lean:

```lean
theorem aime_1983_p3 (f : ℝ → ℝ)
    (h₀ : ∀ x, f x = x ^ 2 + (18 * x + 30) - 2 * Real.sqrt (x ^ 2 + (18 * x + 45)))
    (h₁ : Fintype (f ⁻¹' {0})) : ∏ x ∈ (f ⁻¹' {0}).toFinset, x = 20
```

## aime_1989_p8

- Split: **test** · Dificultad: avanzado · Área: algebra (`heuristica`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> Assume that $x_1,x_2,\ldots,x_7$ are real numbers such that \[ \begin{array}{r} x_1+4x_2+9x_3+16x_4+25x_5+36x_6+49x_7=1\,\,\,\,\,\,\,\, \\ 4x_1+9x_2+16x_3+25x_4+36x_5+49x_6+64x_7=12\,\,\,\,\, \\ 9x_1+16x_2+25x_3+36x_4+49x_5+64x_6+81x_7=123. \\ \end{array} \] Find the value of \[16x_1+25x_2+36x_3+49x_4+64x_5+81x_6+100x_7.\]

Lean:

```lean
theorem aime_1989_p8 (a b c d e f g : ℝ)
    (h₀ : a + 4 * b + 9 * c + 16 * d + 25 * e + 36 * f + 49 * g = 1)
    (h₁ : 4 * a + 9 * b + 16 * c + 25 * d + 36 * e + 49 * f + 64 * g = 12)
    (h₂ : 9 * a + 16 * b + 25 * c + 36 * d + 49 * e + 64 * f + 81 * g = 123) :
    16 * a + 25 * b + 36 * c + 49 * d + 64 * e + 81 * f + 100 * g = 334
```

## aime_1990_p15

- Split: **test** · Dificultad: avanzado · Área: algebra (`heuristica`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> Find $ax^5 + by^5$ if the real numbers $a$, $b$, $x$, and $y$ satisfy the equations \begin{eqnarray*} ax + by &=& 3, \\ ax^2 + by^2 &=& 7, \\ ax^3 + by^3 &=& 16, \\ ax^4 + by^4 &=& 42. \end{eqnarray*}

Lean:

```lean
theorem aime_1990_p15 (a b x y : ℝ) (h₀ : a * x + b * y = 3) (h₁ : a * x ^ 2 + b * y ^ 2 = 7)
    (h₂ : a * x ^ 3 + b * y ^ 3 = 16) (h₃ : a * x ^ 4 + b * y ^ 4 = 42) :
    a * x ^ 5 + b * y ^ 5 = 20
```

## aime_1991_p9

- Split: **test** · Dificultad: avanzado · Área: algebra (`heuristica`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> Suppose that $\sec x+\tan x=\frac{22}7$ and that $\csc x+\cot x=\frac mn,$ where $\frac mn$ is in lowest terms. Find $m+n.$

Lean:

```lean
theorem aime_1991_p9 (x : ℝ) (m : ℚ) (h₀ : 1 / Real.cos x + Real.tan x = 22 / 7)
    (h₁ : 1 / Real.sin x + 1 / Real.tan x = m) : ↑m.den + m.num = 44
```

## mathd_algebra_441

- Split: **test** · Dificultad: basico · Área: algebra (`nombre`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> Assuming $x\ne0$, simplify $\frac{12}{x \cdot x} \cdot \frac{x^4}{14x}\cdot \frac{35}{3x}$.

Lean:

```lean
theorem mathd_algebra_441 (x : ℝ) (h₀ : x ≠ 0) :
    12 / (x * x) * (x ^ 4 / (14 * x)) * (35 / (3 * x)) = 10
```

## amc12a_2008_p25

- Split: **test** · Dificultad: intermedio · Área: algebra (`heuristica`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> A sequence $ (a_1,b_1)$, $ (a_2,b_2)$, $ (a_3,b_3)$, $ \ldots$ of points in the coordinate plane satisfies \[ (a_{n +{} 1}, b_{n +{} 1}) ={} (\sqrt {3}a_n -{} b_n, \sqrt {3}b_n +{} a_n)\hspace{3ex}\text{for}\hspace{3ex} n ={} 1,2,3,\ldots.\] Suppose that $ (a_{100},b_{100}) ={} (2,4)$. What is $ a_1 +{} b_1$? $ \textbf{(A)}\-{} \frac {1}{2^{97}} \qquad \textbf{(B)}\-{} \frac {1}{2^{99}} \qquad \textbf{(C)}\ 0 \qquad \textbf{(D)}\ \frac {1}{2^{98}} \qquad \textbf{(E)}\ \frac {1}{2^{96}}$

Lean:

```lean
theorem amc12a_2008_p25 (a b : ℕ → ℝ) (h₀ : ∀ n, a (n + 1) = Real.sqrt 3 * a n - b n)
    (h₁ : ∀ n, b (n + 1) = Real.sqrt 3 * b n + a n) (h₂ : a 100 = 2) (h₃ : b 100 = 4) :
    a 1 + b 1 = 1 / 2 ^ 98
```

## mathd_algebra_170

- Split: **test** · Dificultad: basico · Área: conteo (`enunciado`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> How many integers are in the solution set of $|x-2|\leq5.6$ ?

Lean:

```lean
theorem mathd_algebra_170 (S : Finset ℤ) (h₀ : ∀ n : ℤ, n ∈ S ↔ abs (n - 2) ≤ 5 + 6 / 10) :
    S.card = 11
```

## amc12a_2003_p23

- Split: **test** · Dificultad: intermedio · Área: conteo (`enunciado`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> How many perfect squares are divisors of the product $ 1!\cdot 2!\cdot 3!\cdots 9!$? $ \textbf{(A)}\ 504 \qquad \textbf{(B)}\ 672 \qquad \textbf{(C)}\ 864 \qquad \textbf{(D)}\ 936 \qquad \textbf{(E)}\ 1008$

Lean:

```lean
theorem amc12a_2003_p23 (S : Finset ℕ)
    (h₀ : ∀ k : ℕ, k ∈ S ↔ 0 < k ∧ (k * k : ℕ) ∣ ∏ i ∈ Finset.Icc 1 9, i !) : S.card = 672
```

## amc12a_2020_p4 ★ FIDELIDAD

- Split: **test** · Dificultad: intermedio · Área: conteo (`enunciado`)
- [ ] Área correcta   - [ ] Fidelidad correcta
- Observaciones: 

Lenguaje natural:

> How many $4$-digit positive integers (that is, integers between $1000$ and $9999$, inclusive) having only even digits are divisible by $5?$ $\textbf{(A) } 80 \qquad \textbf{(B) } 100 \qquad \textbf{(C) } 125 \qquad \textbf{(D) } 200 \qquad \textbf{(E) } 500$

Lean:

```lean
theorem amc12a_2020_p4 (S : Finset ℕ)
    (h₀ : ∀ n : ℕ, n ∈ S ↔ 1000 ≤ n ∧ n ≤ 9999 ∧ (∀ d : ℕ, d ∈ Nat.digits 10 n → Even d) ∧ 5 ∣ n) :
    S.card = 100
```

## amc12a_2020_p9

- Split: **test** · Dificultad: intermedio · Área: conteo (`enunciado`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> How many solutions does the equation $\tan{(2x)} = \cos{(\tfrac{x}{2})}$ have on the interval $[0, 2\pi]?$ $\textbf{(A) } 1 \qquad \textbf{(B) } 2 \qquad \textbf{(C) } 3 \qquad \textbf{(D) } 4 \qquad \textbf{(E) } 5$

Lean:

```lean
theorem amc12a_2020_p9 (S : Finset ℝ)
    (h₀ : ∀ x : ℝ, x ∈ S ↔ 0 ≤ x ∧ x ≤ 2 * Real.pi ∧ Real.tan (2 * x) = Real.cos (x / 2)) :
    S.card = 5
```

## amc12b_2020_p21

- Split: **test** · Dificultad: intermedio · Área: conteo (`enunciado`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> How many positive integers $n$ satisfy$$\dfrac{n+1000}{70} = \lfloor \sqrt{n} \rfloor?$$(Recall that $\lfloor x\rfloor$ is the greatest integer not exceeding $x$.) $\textbf{(A) } 2 \qquad\textbf{(B) } 4 \qquad\textbf{(C) } 6 \qquad\textbf{(D) } 30 \qquad\textbf{(E) } 32$

Lean:

```lean
theorem amc12b_2020_p21 (S : Finset ℕ)
    (h₀ : ∀ n : ℕ, n ∈ S ↔ 0 < n ∧ (↑n + (1000 : ℝ)) / 70 = Int.floor (Real.sqrt n)) : S.card = 6
```

## amc12b_2021_p1 ★ FIDELIDAD

- Split: **test** · Dificultad: intermedio · Área: conteo (`enunciado`)
- [ ] Área correcta   - [ ] Fidelidad correcta
- Observaciones: 

Lenguaje natural:

> How many integer values satisfy $|x|< 3\pi$? $\textbf{(A) }9 \qquad \textbf{(B) }10 \qquad \textbf{(C) }18 \qquad \textbf{(D) }19 \qquad \textbf{(E) }20$

Lean:

```lean
theorem amc12b_2021_p1 (S : Finset ℤ) (h₀ : ∀ x : ℤ, x ∈ S ↔ ↑(abs x) < 3 * Real.pi) :
    S.card = 19
```

## amc12b_2021_p13

- Split: **test** · Dificultad: intermedio · Área: conteo (`enunciado`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> How many values of $\theta$ in the interval $0<\theta\le 2\pi$ satisfy $$1-3\sin\theta+5\cos3\theta=0?$$ $\textbf{(A) }2 \qquad \textbf{(B) }4 \qquad \textbf{(C) }5\qquad \textbf{(D) }6 \qquad \textbf{(E) }8$

Lean:

```lean
theorem amc12b_2021_p13 (S : Finset ℝ)
    (h₀ :
      ∀ x : ℝ, x ∈ S ↔ 0 < x ∧ x ≤ 2 * Real.pi ∧ 1 - 3 * Real.sin x + 5 * Real.cos (3 * x) = 0) :
    S.card = 6
```

## aime_1994_p3

- Split: **test** · Dificultad: avanzado · Área: teoria_de_numeros (`heuristica`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> The function $f$ has the property that, for each real number $x,$ \[ f(x)+f(x-1) = x^2. \] If $f(19)=94,$ what is the remainder when $f(94)$ is divided by 1000?

Lean:

```lean
theorem aime_1994_p3 (f : ℤ → ℤ) (h0 : ∀ x, f x + f (x - 1) = x ^ 2) (h1 : f 19 = 94) :
    f 94 % 1000 = 561
```

## imo_1959_p1

- Split: **test** · Dificultad: avanzado · Área: teoria_de_numeros (`heuristica`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> Prove that the fraction $ \dfrac{21n +{} 4}{14n +{} 3}$ is irreducible for every natural number $ n$.

Lean:

```lean
theorem imo_1959_p1 (n : ℕ) (h₀ : 0 < n) : Nat.gcd (21 * n + 4) (14 * n + 3) = 1
```

## imo_1984_p6 ★ FIDELIDAD

- Split: **test** · Dificultad: avanzado · Área: teoria_de_numeros (`heuristica`)
- [ ] Área correcta   - [ ] Fidelidad correcta
- Observaciones: 

Lenguaje natural:

> Let $a,b,c,d$ be odd integers such that $0< a< b< c< d$ and $ad=bc$. Prove that if $a+d=2^k$ and $b+c=2^m$ for some integers $k$ and $m$, then $a=1$.

Lean:

```lean
theorem imo_1984_p6 (a b c d k m : ℕ) (h₀ : 0 < a ∧ 0 < b ∧ 0 < c ∧ 0 < d)
    (h₁ : Odd a ∧ Odd b ∧ Odd c ∧ Odd d) (h₂ : a < b ∧ b < c ∧ c < d) (h₃ : a * d = b * c)
    (h₄ : a + d = 2 ^ k) (h₅ : b + c = 2 ^ m) : a = 1
```

## mathd_numbertheory_353

- Split: **test** · Dificultad: basico · Área: teoria_de_numeros (`nombre`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> Let $S = 2010 + 2011 + \cdots + 4018$. Compute the residue of $S$, modulo 2009.

Lean:

```lean
theorem mathd_numbertheory_353 (s : ℕ) (h₀ : s = ∑ k ∈ Finset.Icc 2010 4018, k) : s % 2009 = 0
```

## mathd_numbertheory_430

- Split: **test** · Dificultad: basico · Área: teoria_de_numeros (`nombre`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> If $A$, $B$, and $C$ represent three distinct digits from 1 to 9 and they satisfy the following equations, what is the value of the sum $A+B+C$? (In the equation below, $AA$ represents a two-digit number both of whose digits are $A$.) $$A+B=C$$$$AA-B=2\times C$$$$C\times B=AA+A$$

Lean:

```lean
theorem mathd_numbertheory_430 (a b c : ℕ) (h₀ : 1 ≤ a ∧ a ≤ 9) (h₁ : 1 ≤ b ∧ b ≤ 9)
    (h₂ : 1 ≤ c ∧ c ≤ 9) (h₃ : a ≠ b) (h₄ : a ≠ c) (h₅ : b ≠ c) (h₆ : a + b = c)
    (h₇ : 10 * a + a - b = 2 * c) (h₈ : c * b = 10 * a + a + a) : a + b + c = 8
```

## amc12_2001_p5

- Split: **test** · Dificultad: intermedio · Área: teoria_de_numeros (`heuristica`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> What is the product of all odd positive integers less than 10000? $ \textbf{(A)} \ \frac {10000!}{(5000!)^2} \qquad \textbf{(B)} \ \frac {10000!}{2^{5000}} \ \qquad \textbf{(C)} \ \frac {9999!}{2^{5000}} \qquad \textbf{(D)} \ \frac {10000!}{2^{5000} \cdot 5000!} \qquad \textbf{(E)} \ \frac {5000!}{2^{5000}}$

Lean:

```lean
theorem amc12_2001_p5 :
    Finset.prod (Finset.filter (fun x => ¬Even x) (Finset.range 10000)) (id : ℕ → ℕ) =
      10000! / (2 ^ 5000 * 5000!)
```

## amc12a_2021_p8

- Split: **test** · Dificultad: intermedio · Área: teoria_de_numeros (`heuristica`)
- [ ] Área correcta
- Observaciones: 

Lenguaje natural:

> A sequence of numbers is defined by $D_0=0,D_1=0,D_2=1$ and $D_n=D_{n-1}+D_{n-3}$ for $n\ge 3$. What are the parities (evenness or oddness) of the triple of numbers $(D_{2021},D_{2022},D_{2023})$, where $E$ denotes even and $O$ denotes odd? $\textbf{(A) }(O,E,O) \qquad \textbf{(B) }(E,E,O) \qquad \textbf{(C) }(E,O,E) \qquad \textbf{(D) }(O,O,E) \qquad \textbf{(E) }(O,O,O)$

Lean:

```lean
theorem amc12a_2021_p8 (d : ℕ → ℕ) (h₀ : d 0 = 0) (h₁ : d 1 = 0) (h₂ : d 2 = 1)
    (h₃ : ∀ n ≥ 3, d n = d (n - 1) + d (n - 3)) : Even (d 2021) ∧ Odd (d 2022) ∧ Even (d 2023)
```
