# Política de privacidad

**Versión 2026-09-28.** Esta página explica qué datos guarda LARIA, para qué, con quién los comparte y cómo puedes borrarlos. Está escrita a partir de lo que el sistema hace de verdad, no de una plantilla.

## Quién es responsable

El responsable del tratamiento de tus datos es **[[COMPLETAR: nombre de la persona u organización responsable]]**, con domicilio en **[[COMPLETAR: país y ciudad]]**. Para cualquier cuestión sobre tus datos puedes escribir a **[[COMPLETAR: correo de contacto]]**.

## Qué datos guardamos

**Tu cuenta.** Tu nombre de usuario, tu correo electrónico y tu contraseña. La contraseña nunca se guarda tal cual: se guarda cifrada con bcrypt, de forma que ni siquiera nosotros podemos leerla.

**Lo que subes y escribes.**
- Los documentos que subes: el archivo original y el texto que extraemos de él.
- Tus chats con el tutor, con todos sus mensajes.
- Los cuestionarios y nivelaciones que haces, y tus respuestas.

**Tu perfil de aprendizaje.** Es lo que permite que el tutor se adapte a ti. Se calcula a partir de lo que haces en la plataforma y contiene:
- Cuánto dominas cada concepto y cada documento, estimado a partir de tus respuestas.
- Tu nivel en cada tema en el que te hayas nivelado (básico, intermedio o avanzado).
- Señales sobre **cómo** aprendes: por ejemplo, si sueles pedir ejemplos, si abandonas las explicaciones largas o cuánto tiempo pasa entre tus mensajes.
- Los errores frecuentes, tu ritmo y el estilo de explicación que mejor te ha funcionado.

**Datos técnicos.**
- Tu dirección IP, que usamos solo para limitar el número de peticiones y proteger el servicio de abusos. Se guarda durante aproximadamente un minuto.
- Registros técnicos del servidor: qué rutas se llamaron, cuándo y cuánto tardaron. No contienen el texto de tus mensajes ni tu correo.

**Lo que no guardamos.** No pedimos tu nombre real, tu edad, tu dirección ni ningún dato de pago.

## Para qué los usamos

- **Para enseñarte:** responder tus preguntas, generar cuestionarios de tu material y nivelarte.
- **Para adaptarnos a ti:** con tu perfil de aprendizaje, el tutor decide cómo explicarte, con qué dificultad y qué recomendarte repasar. Es una decisión automatizada, pero solo afecta a cómo te enseña: **no te califica, no te certifica y no tiene efectos fuera de la plataforma.** Además, cuando adapta su forma de explicar, el tutor te dice por qué.
- **Para mantener el servicio seguro y funcionando.**

**No vendemos tus datos, no los usamos para publicidad y no entrenamos modelos de inteligencia artificial con ellos.**

## Con quién los compartimos

Para funcionar, LARIA se apoya en estos proveedores. Todos están en **Estados Unidos**, así que tus datos salen de tu país:

| Proveedor | Para qué | Qué datos recibe |
|---|---|---|
| **OpenAI** | Generar las respuestas del tutor, analizar documentos y crear cuestionarios | El texto de tus documentos, tus preguntas y la conversación reciente del chat |
| **Render** (Oregón) | Alojar el servidor de la aplicación | Todo lo que pasa por la aplicación |
| **MongoDB Atlas** (Virginia) | Guardar tu cuenta, tus chats y tu perfil | Todos los datos descritos arriba, salvo los archivos originales |
| **Cloudflare R2** | Guardar los archivos originales que subes | Tus documentos originales |
| **Upstash** (Oregón) | Caché de respuestas y límite de peticiones | Tu IP y respuestas generadas, de forma temporal |
| **Vercel** (Virginia) | Alojar la página web | Datos técnicos de navegación |
| **Google Fonts** | Servir una de las tipografías de la web | Tu dirección IP al descargar la fuente |

Sobre OpenAI: según sus condiciones para la API, los datos enviados por esta vía no se usan para entrenar sus modelos. **[[COMPLETAR: verificar con la política vigente de OpenAI antes de publicar]]**.

## Cuánto tiempo los guardamos

- **Tu cuenta, tus documentos, tus chats y tu perfil:** hasta que los borres tú. Borrar un documento borra también sus cuestionarios, tus respuestas a ellos y su rastro en tu perfil.
- **Las respuestas generadas en caché:** caducan solas. Las respuestas del tutor, en 1 hora; los cuestionarios, en 24 horas; los análisis de documentos, en 7 días.
- **Tu IP para el límite de peticiones:** aproximadamente 1 minuto.
- **Los registros técnicos:** el tiempo que los conserve el proveedor de alojamiento.

## Tus derechos

- **Ver tus datos.** Tu historial y tu perfil de aprendizaje se pueden consultar dentro de la aplicación. Para una copia completa, escríbenos a **[[COMPLETAR: correo de contacto]]**.
- **Borrar tu cuenta y todos tus datos.** Puedes hacerlo tú mismo desde la aplicación, confirmando con tu contraseña. Se borran tu cuenta, tus documentos y sus archivos originales, tus chats, cuestionarios, nivelaciones, respuestas y tu perfil de aprendizaje. **No se puede deshacer.** Lo único que queda son las respuestas en caché, que caducan solas en un máximo de 7 días, y los registros técnicos del servidor, que no contienen el contenido de lo que escribiste.
- **Corregir tus datos, oponerte o presentar una reclamación:** escríbenos a **[[COMPLETAR: correo de contacto]]**. También puedes acudir a la autoridad de protección de datos de tu país: **[[COMPLETAR: autoridad competente según la jurisdicción]]**.

## Menores de edad

**[[COMPLETAR: edad mínima para usar LARIA y cómo se obtiene el consentimiento de madres, padres o tutores legales. Hoy el registro no pide la edad.]]**

## Seguridad

Todas las comunicaciones viajan cifradas (HTTPS/TLS), también entre nuestros servidores y la base de datos. Las contraseñas se guardan cifradas y exigen al menos 12 caracteres con mayúsculas, minúsculas y números. Solo tú puedes ver tus documentos y tus chats.

## Cambios en esta política

Si cambiamos algo importante te lo avisaremos en la aplicación. Cada versión de esta página lleva su fecha.
