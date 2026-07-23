# 🚀 [Plantilla de Chatbot AI con Astro - Edición Vercel SDK](https://template-astro-vercel-sdk-ai-chatbo.vercel.app/)

<div align="center">

<img src="https://github.com/user-attachments/assets/7191280a-c335-415e-a74c-307e9174ce84"
     alt="Plantilla Astro"
     width="1920" height="1080"
     style="display:block; margin-bottom:20px;" />

![Astro](https://astro.build/assets/press/astro-icon-light-gradient.svg)

[![Disponible en](https://img.shields.io/badge/Disponible%20en-Astro%20Themes-purple?style=for-the-badge&link=https://astro.build/themes/)](https://portal.astro.build/themes/ai-chat-bot/) 

[![Astro](https://img.shields.io/badge/Astro-0C1222?style=for-the-badge&logo=astro&logoColor=FDFDFE)](https://astro.build) [![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org) [![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org) [![TailwindCSS](https://img.shields.io/badge/TailwindCSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com) [![Vercel AI SDK](https://img.shields.io/badge/Vercel%20AI%20SDK-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://sdk.vercel.ai) [![Prompt Kit](https://img.shields.io/badge/Prompt%20Kit-FF6B6B?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0IiByeD0iNCIgZmlsbD0iI0ZGNjI2QiIvPgo8cGF0aCBkPSJNMTIgN2w0IDQgNCA0djEwYzAtNC40LTMuNi0zLjYtMy42LTMuNnoiIGZpbGw9IiMwMDAwMDAiLz4KPHBhdGggZD0iTTEyIDE3bC00LTRsNC00djhoIiBmaWxsPSIjMDAwMDAwIi8+Cjwvc3ZnPgo=)](https://prompt-kit.dev)

</div>

## 🌟 Descripción general

La Plantilla de Chatbot AI con Astro es una plantilla moderna y lista para producción para construir interfaces de chat impulsadas por IA. Construida con Astro, React y el SDK de Vercel AI, proporciona una interfaz hermosa y responsiva con implementaciones simuladas que puedes reemplazar fácilmente por proveedores de IA reales.

Perfecta para desarrolladores que quieren iniciar rápidamente aplicaciones de chat con IA con soporte para múltiples proveedores, historial de conversaciones, carga de archivos y una experiencia de usuario pulida.

## 🚀 Inicio rápido

1. **Clonar e instalar**

   ```bash
   git clone https://github.com/Marve10s/Astro-Vercel-SDK-AI-Chatbot.git
   cd Astro-Vercel-SDK-AI-Chatbot
   pnpm install
   ```

   **O hacer fork e instalar**

   1.1 Haz clic en el botón 'Fork' en la esquina superior derecha de este repositorio

   1.2 Clona tu repositorio bifurcado

   ```bash
   git clone https://github.com/TU_USUARIO/Astro-Vercel-SDK-AI-Chatbot.git
   cd Astro-Vercel-SDK-AI-Chatbot && pnpm install
   ```

2. **Desarrollo**

   ```bash
   pnpm dev
   ```

3. **Configurar el entorno**

   ```bash
   cp .env.example .env.local
   ```

   Añade tus claves API para los proveedores que quieras usar:
   - OpenAI (`OPENAI_API_KEY`)
   - Anthropic (`ANTHROPIC_API_KEY`)
   - Google Gemini (`GOOGLE_GENERATIVE_AI_API_KEY`)
   - Groq (`GROQ_API_KEY`)

4. **Compilar**

   ```bash
   pnpm build
   pnpm preview
   ```

## ⭐ Características

- 🤖 **Múltiples proveedores AI** - OpenAI, Anthropic, Google Gemini, Groq
- 💬 **Streaming en tiempo real** - Respuestas token por token
- 📁 **Carga de archivos** - Soporte para adjuntar imágenes
- 🌙 **Modo oscuro/claro** - Cambio de tema integrado
- 💾 **Historial de conversaciones** - Sesiones de chat persistentes
- 📱 **Diseño responsivo** - Enfoque mobile-first
- 🎨 **Interfaz hermosa** - Diseño moderno con Tailwind CSS
- ⚡ **Rendimiento rápido** - Generación estática de Astro + islas React
- 🔧 **TypeScript** - Seguridad de tipos completa
- 🧩 **Componentes modulares** - Fáciles de personalizar y extender

## 📁 Estructura del proyecto

```plaintext
/
├── public/              # Archivos estáticos
├── src/
│   ├── components/
│   │   ├── Chatbot.tsx          # Interfaz principal del chat
│   │   ├── ThemeToggle.tsx      # Cambiador de tema
│   │   ├── prompt-kit/          # Primitivas UI
│   │   │   ├── chat-container.tsx
│   │   │   ├── message.tsx
│   │   │   ├── prompt-input.tsx
│   │   │   └── ...
│   │   └── ui/                  # Componentes UI compartidos
│   ├── lib/
│   │   └── utils.ts             # Funciones utilitarias
│   ├── mocks/                   # Implementaciones simuladas
│   │   ├── ai-vercel-sdk.ts     # Mocks de proveedores AI
│   │   └── supabase.ts          # Mocks de base de datos
│   ├── pages/
│   │   └── index.astro          # Página principal
│   └── styles/
│       └── global.css           # Estilos globales + Tailwind
├── astro.config.mjs     # Configuración de Astro
├── tailwind.config.mjs  # Configuración de Tailwind
└── package.json
```

## 📊 Rendimiento

<div>

[![PageSpeed Desktop](https://img.shields.io/badge/PageSpeed%20Desktop-98-success?style=for-the-badge&logo=pagespeed-insights)](https://pagespeed.web.dev/)

| Métrica            | Puntaje |
| ----------------- | ------- |
| 🚀 Rendimiento    | 98/100  |
| ♿ Accesibilidad  | 96/100  |
| 🏗️ Buenas prácticas | 100/100 |
| 🔍 SEO            | 100/100 |

</div>

## 🛠️ Personalización

### Proveedores AI

Añade soporte para nuevos proveedores AI extendiendo las implementaciones simuladas en `src/mocks/ai-vercel-sdk.ts`:

```typescript
export type Provider = "openai" | "anthropic" | "google" | "groq" | "tu-proveedor";
```

### Componentes UI

- Modifica `src/components/prompt-kit/` para cambios principales de UI
- Añade componentes personalizados en `src/components/`
- Personaliza los temas en `src/styles/global.css`

### Integración con backend

Reemplaza las funciones simuladas con llamadas API reales:

```typescript
// Reemplaza esto en Chatbot.tsx
import { generateChat } from "@/mocks/ai-vercel-sdk";

// Con tu implementación real
import { generateChat } from "@/lib/ai-service";
```

## 🚀 Despliegue

### Vercel (Recomendado)

1. Sube a GitHub
2. Conecta con Vercel
3. Añade las variables de entorno
4. ¡Despliega!

### Otras plataformas

La plantilla funciona con cualquier servicio de hosting estático. Para rutas API, usa:

```typescript
// src/pages/api/chat.ts
export const config = { runtime: "edge" };

export async function POST({ request }) {
  // Tu lógica AI aquí
}
```

## 🎨 Comparte tu creación

¿Has construido algo increíble con esta plantilla? ¡Me encantaría verlo!

- Crea un [issue en GitHub](https://github.com/yourusername/astro-ai-chatbot-template/issues) con capturas de pantalla
- Comparte tu enlace de demo y modificaciones

### 🌟 Vitrina comunitaria

Revisa estas increíbles implementaciones de nuestra comunidad:

*[Tu proyecto aquí - ¡sé el primero en mostrarlo!]*

## 📄 Licencia

Este proyecto está licenciado bajo la Licencia MIT - consulta el archivo [LICENSE](LICENSE) para más detalles.

---

<div align="center">

Hecho con ❤️ usando [Astro](https://astro.build) y [Vercel AI SDK](https://sdk.vercel.ai)

</div>
