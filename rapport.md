# Rapport TVID
Fait par : Thomas POLO et Gabriel CELLIER

## Partie A

1 - pendulum.m2v choisit

3 - resolution: 720x720, profondeur: 255 soit 8 bits, sampling mode: Mode Binaire (Raw)

## Partie B

1 - 0x1422

3 - The first few frames look incomplete and at some points it looks like the pixels are jittering.

4 - We can see that the frames go from being progressive to being interlaced.

5 - L'encodeur a configuré le flux comme étant "entrelacé" ou "mixte" (progressive_sequence=0) au niveau global, alors que le contenu est hybride.

6 - L'option heuristique à implémenter serait un désentrelacement adaptatif. Au lieu de forcer le mode Bob (qui dégrade les images progressives) ou de ne rien faire.

## Partie C

1 - 0x3fd

3 - L'image tremble violemment. La vidéo originale est probablement en "Top Field First" (TFF). Cependant, les effets spéciaux ont été générés ou insérés par un système de montage mal configuré ou fonctionnant en "Bottom Field First" (BFF), ou inversement. Le décodeur affiche donc le champ "futur" avant le champ "passé", créant ce tremblement.

4 -  0x3e9

6 - Ce flux est un exemple de Soft Telecine (3:2 Pulldown) pour le contenu film, mélangé avec du contenu vidéo purement entrelacé (les blocs où progressive_frame=0 apparaissent).

### Partie D

2 - L'amélioration est la plus visible sur les zones statiques de l'image pendant les séquences film. Parce que contrairement au mode "Bob" qui divise par deux la résolution verticale même sur les images fixes (rendant l'image floue et scintillante), l'approche adaptative préserve la pleine résolution (mode "Weave") sur les zones immobiles, n'activant la réduction de définition (désentrelacement) que là où il y a du mouvement pour éviter l'effet de peigne.

