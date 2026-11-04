=======================================================
Usando Micropython de verdad: bienvenidos a la robótica
=======================================================
El año pasado, 2025, fue para mí el año de los microcontroladores y de Micropython. Primero con una ponencia en
OpenSouthCode Málaga, y luego aquí, en PyConES en formato de taller. Ambos tuvieron gran acogida, pero en ambos llegaba
siempre la misma pregunta: ¿y esto para qué sirve? ¿de verdad puede usarse Micropython en algo más serio? Pues bien,
vamos a demostrar que Micropython puede usarse en proyectos más serios. Y lo vamos a hacer, desde el mundo de la
robótica. Bienvenidos todos a la robótica con Micropython.

Nuestro robot será Stack-chan, un adorable robot opensource y hardware libre ya montado y de precio asequible,
que programaremos en Micropython.

📽️ La **presentación** está `disponible online <https://nekmo.github.io/micropython-robotica-presentacion/>`_ ya
compilada para su visualización.

✏️ Todos los **ejemplos** están en la carpeta `demos <demos/>`_ y pueden ejecutarse en el robot o en el simulador.


Contenido
---------

* Bienvenida e introducción.
* Qué es Micropython y su uso en microcontroladores.
* Casos de uso: programar a Stack-chan.
* Primer reto: controlar los servos.
* Segundo reto: sensores del robot.
* Tercer reto: micrófono y cámara.
* Cuarto reto: dibujar en la pantalla.
* Quinto reto: inteligencia artificial en un ESP32.
* Demostración completa con Stack-chan.
* Punto final a la presentación.


Demos en directo
----------------
La presentación es autocontenida: no necesita Internet ni programas externos. Las diapositivas de demo incluyen un
editor (Monaco) que ejecuta el código en uno de estos destinos:

* **Robot (USB)**: Stack-chan con UIFlow 2 conectado por USB. Usa Web Serial, por lo que requiere Chrome o Edge y
  servir la presentación desde ``localhost`` o HTTPS (``make serve``).
* **Simulador**: Stack-chan simulado dentro del navegador. Es MicroPython compilado a WebAssembly ejecutándose en un
  Web Worker, con los módulos del robot (``M5``, ``hardware.stackchan``, ``lvgl``, ``m5ui``, ``machine``, ``camera``,
  ``requests``...) simulados. Los *shims* están adaptados de `esp-emulator`. El recuadro de cámara muestra el robot en
  3D (servos, LEDs y pantalla) con controles para tocar la cabeza, agitarlo, inclinarlo, acercar la mano o usar el
  micrófono real. La cámara del simulador usa la webcam y ``requests`` hace las peticiones desde el navegador.

El simulador necesita ``SharedArrayBuffer``. GitHub Pages no permite enviar las cabeceras COOP/COEP, así que
``coi-sw.js`` (un *service worker* en la raíz del sitio) las añade y la página se recarga una vez al abrirla.

Atajos:

* ``Ctrl+Enter`` en el editor ejecuta el código.
* ``C`` cambia la fuente del recuadro de cámara: cámara o simulador.
* ``Ctrl+F11`` pone la cámara a pantalla completa.
* El botón *Ajustes* (abajo a la izquierda) elige la cámara, el modo espejo, el zoom y la clave de API que usará el
  simulador en la demo de Claude (se guarda solo en este navegador).

Robot
-----
La carpeta ``robot`` contiene el port del firmware de Stack-chan a Micropython (``libs/stackchan`` y sus imágenes),
que usan las demos ``demo9_avatar`` y ``demo12_final``. El simulador lo incluye automáticamente; para el robot real::

    make upload     # sube robot/libs y robot/res con mpytool

La demo ``demo11_claude`` necesita un ``secrets.py`` en el robot (ver ``demos/demo11_claude/secrets.example.py``).
La detección de caras (``demo10``) usa el módulo ``dl`` de UIFlow 2: en el simulador se ejecuta, pero no detecta nada.


Modelo 3D
---------
El modelo 3D de Stack-chan está en ``models/stackchan.blend`` (Blender 5.0). La presentación usa
``_static/models/stackchan.glb``, generado con ``models/export_stackchan.py``, que sustituye los materiales del
original (casi negros) por los colores del StackChan real (carcasa gris claro, frontal negro, aro de cámara
naranja y base gris oscura) y añade los pivotes de los servos (``yaw`` y ``pitch``),
el plano de la cara, los 12 LEDs y las 3 zonas táctiles, enrasados en la parte superior de la cabeza::

    make model      # requiere blender en el PATH (o BLENDER=/ruta/a/blender)


Dependencias incluidas
----------------------
Todo lo que la presentación carga está en el repositorio, en ``_static/vendor``:

* MicroPython 1.29 para WebAssembly (MIT).
* Monaco Editor 0.57, sin los *workers* de otros lenguajes (MIT).
* three.js 0.187 y su cargador glTF (MIT).
* Tipografías Dela Gothic One, M PLUS 1p y JetBrains Mono, subconjuntos latinos (SIL OFL 1.1).


Diseño
------
La presentación es un juego de planos técnicos de un robot pequeño: las diapositivas claras son hojas de dibujo sobre el
plástico blanco de Stack-chan, las oscuras son planos en tinta, y los títulos de sección ocurren en la propia pantalla
del robot, con su cara viva que sigue al puntero y parpadea. Cada diapositiva declara su escena con
``:data-scene:`` (``face``, ``sheet``, ``blueprint`` o ``neon``) y su cajetín con ``:data-sheet:``.

Directivas propias (``stackchan_ext.py``):

* ``micropython-demo``: editor en vivo. Opciones ``:file:``, ``:height:``.
* ``stackchan-3d``: modelo 3D (three.js). ``:mode:`` ``anatomy``, ``servos`` o ``mirror`` (sigue al simulador;
  con ``:file:`` añade un botón para ejecutar ese programa).
* ``stackchan-face``: la cara animada de Stack-chan.
* ``camera-view``: hueco donde se acopla la cámara en vivo.


Compilación
-----------
Requiere Python 3.12+ y ``sassc``::

    # Instalar dependencias
    pip install -r requirements.txt
    # Compilar estilos y presentación
    make revealjs
    # Servir en http://localhost:8000 (necesario para Web Serial y la cámara)
    make serve

Tras la compilación pueden verse los ficheros resultantes en el directorio ``_build``.


Presentaciones anteriores
=========================

* Charla: `github.com/Nekmo/micropython-presentacion <https://github.com/Nekmo/micropython-presentacion>`_.
* Taller: `github.com/Nekmo/micropython-workshop <https://github.com/Nekmo/micropython-workshop>`_.


Copyright
=========
Licencia MIT. Ver fichero ``LICENSE.txt``.

Nekmo 2026.
