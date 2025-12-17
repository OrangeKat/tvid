# Rapport TVID

**Auteurs :** Thomas POLO et Gabriel CELLIER

---

## Partie A : Jouer un flux MPEG-2 élémentaire de test

**1. Choix de la séquence**
Nous avons choisi le fichier `pendulum.m2v` pour nos expérimentations. Ce flux est un flux élémentaire MPEG-2 (Elementary Stream).

**3. Analyse des images PGM générées**
Après conversion via `mpeg2dec`, nous observons les caractéristiques suivantes dans l'en-tête des fichiers PGM:

* **Format et Magic Number :** Le fichier commence par le magic number **P5**, ce qui correspond au format "binary PGM" (portable graymap).
* **Résolution :** L'image possède une résolution de **720x720** pixels.
* **Profondeur :** La valeur maximale de gris est **255**, ce qui indique une profondeur de couleur de **8 bits** par pixel.
* **Sampling Mode :** Il s'agit d'un mode binaire.

---

## Partie B : Jouer un flux vidéo de chaîne d'infos américaine (`cnn.ts`)

**1. Identification du PID vidéo**
En analysant le fichier `cnn.ts` avec `ffplay` ou via l'option `-t` de `mpeg2dec`, nous avons identifié que le PID du flux vidéo est **0x1422**.

**3. Observation après désentrelacement**
Après avoir converti le flux en PGM et appliqué notre désentrelaceur, nous observons plusieurs artefacts:

* Les premières images semblent corrompues ou incomplètes. Cela est dû au fait que le décodage commence sur des frames intermédiaires (B-frames ou P-frames) avant d'avoir reçu une I-frame de référence (GOP ouvert).
* On observe des effets de scintillement ("jitter") sur les contours et les textes défilants, caractéristiques d'une mauvaise gestion de l'ordre des champs ou d'un désentrelacement imparfait (aliasing temporel).

**4. Analyse des flags `progressive_frame` et `top_field_first**`
En loggant les flags frame par frame, nous constatons que leur état change au cours du flux. Certaines séquences passent de "progressif" à "entrelacé", indiquant un contenu hybride ou une signalisation instable.

**5. Analyse du flag `progressive_sequence` et erreur de l'encodeur**
Nous constatons que L'encodeur a configuré le flux comme étant "entrelacé" ou "mixte" (progressive_sequence=0) au niveau global, alors que le contenu est hybride.

**6. Heuristique de correction**
Pour jouer convenablement ce fichier malgré l'erreur de signalisation, il faut implémenter une heuristique qui **ignore le flag global `progressive_sequence**` si des artefacts d'entrelacement sont détectés, ou forcer un désentrelacement adaptatif basé sur l'analyse des pixels (comparaison des lignes paires et impaires) plutôt que de se fier aveuglément aux métadonnées du flux.

---

## Partie C : Jouer un flux vidéo de chaînes de divertissement asiatiques (`ctv.ts`)

**1. Troisième PID vidéo**
L'analyse des programmes du Transport Stream `ctv.ts` nous permet d'identifier le troisième PID vidéo : **0x3fd**.

**3. Analyse des artefacts (Le gâteau)**
En jouant ce flux, l'image tremble violemment, particulièrement visible sur la séquence du gâteau lors des transitions ou effets spéciaux. Ce problème est dû une inversion de la dominance de champ (**Field Dominance**). La vidéo principale est probablement encodée en *Top Field First* (TFF), mais les effets spéciaux ont été montés ou insérés en *Bottom Field First* (BFF), ou inversement. Ducoup le décodeur affiche le champ temporellement "futur" avant le champ "passé", créant un retour en arrière visuel à chaque image (tremblement) sur ces zones spécifiques.

**4. Premier PID vidéo**
Le premier PID vidéo identifié dans ce flux est **0x3e9**.

**6. Particularité de la signalisation (Soft Telecine)**
En observant les flags de ce premier flux, nous rencontrons une structure typique du **Soft Telecine** (3:2 Pulldown).

* Le flux contient du matériel film (24 images/s) converti pour un affichage télévisé (30 images/s environ).
* Pour cela, les flags `repeat_first_field` et `top_field_first` s'activent cycliquement pour demander au décodeur de répéter certains champs, mélangeant ainsi des images progressives reconstruites et des séquences purement entrelacées.

---

## Partie D : Vers un meilleur désentrelaceur

**2. Améliorations visuelles**
L'amélioration est la plus visible sur les zones statiques de l'image pendant les séquences film. Parce que contrairement au mode "Bob" qui divise par deux la résolution verticale même sur les images fixes (rendant l'image floue et scintillante), l'approche adaptative préserve la pleine résolution (mode "Weave") sur les zones immobiles, n'activant la réduction de définition (désentrelacement) que là où il y a du mouvement pour éviter l'effet de peigne. 
