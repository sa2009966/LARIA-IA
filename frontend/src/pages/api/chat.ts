import type { APIRoute } from 'astro';
import { streamText } from 'ai';
import { createOpenAI } from '@ai-sdk/openai';
import { createAnthropic } from '@ai-sdk/anthropic';
import { createGoogleGenerativeAI } from '@ai-sdk/google';
import { createGroq } from '@ai-sdk/groq';

function getEnv(key: string): string | undefined {
  return (import.meta.env as any)[key] ?? process.env[key];
}

export const POST: APIRoute = async ({ request }) => {
  try {
    const { messages, provider, model } = await request.json();

    if (!messages || !Array.isArray(messages) || messages.length === 0) {
      return new Response(JSON.stringify({ error: 'Se requieren mensajes' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    if (!model) {
      return new Response(JSON.stringify({ error: 'Se requiere un modelo' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    let modelInstance;

    switch (provider) {
      case 'openai': {
        const key = getEnv('OPENAI_API_KEY') || getEnv('AI_API_KEY');
        if (!key) {
          return new Response(
            JSON.stringify({ error: 'Falta API key de OpenAI. Configura OPENAI_API_KEY en .env' }),
            { status: 400, headers: { 'Content-Type': 'application/json' } },
          );
        }
        const openai = createOpenAI({ apiKey: key });
        modelInstance = openai(model as Parameters<typeof openai>[0]);
        break;
      }
      case 'anthropic': {
        const key = getEnv('ANTHROPIC_API_KEY') || getEnv('AI_API_KEY');
        if (!key) {
          return new Response(
            JSON.stringify({ error: 'Falta API key de Anthropic. Configura ANTHROPIC_API_KEY en .env' }),
            { status: 400, headers: { 'Content-Type': 'application/json' } },
          );
        }
        const anthropic = createAnthropic({ apiKey: key });
        modelInstance = anthropic(model as Parameters<typeof anthropic>[0]);
        break;
      }
      case 'google': {
        const key = getEnv('GOOGLE_GENERATIVE_AI_API_KEY') || getEnv('GEMINI_API_KEY') || getEnv('AI_API_KEY');
        if (!key) {
          return new Response(
            JSON.stringify({ error: 'Falta API key de Google. Configura GOOGLE_GENERATIVE_AI_API_KEY en .env' }),
            { status: 400, headers: { 'Content-Type': 'application/json' } },
          );
        }
        const google = createGoogleGenerativeAI({ apiKey: key });
        modelInstance = google(model as Parameters<typeof google>[0]);
        break;
      }
      case 'groq': {
        const key = getEnv('GROQ_API_KEY') || getEnv('AI_API_KEY');
        if (!key) {
          return new Response(
            JSON.stringify({ error: 'Falta API key de Groq. Configura GROQ_API_KEY en .env' }),
            { status: 400, headers: { 'Content-Type': 'application/json' } },
          );
        }
        const groq = createGroq({ apiKey: key });
        modelInstance = groq(model as Parameters<typeof groq>[0]);
        break;
      }
      default:
        return new Response(
          JSON.stringify({ error: `Proveedor no soportado: ${provider}. Usa: openai, anthropic, google, groq` }),
          { status: 400, headers: { 'Content-Type': 'application/json' } },
        );
    }

    const result = streamText({
      model: modelInstance,
      messages: messages.map((m: { role: string; content: string }) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
      })),
    });

    const textStream = result.textStream;
    const readable = new ReadableStream({
      async start(controller) {
        try {
          for await (const chunk of textStream) {
            controller.enqueue(new TextEncoder().encode(chunk));
          }
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Error generando respuesta';
          controller.enqueue(new TextEncoder().encode(`\n\nError: ${errorMessage}`));
        } finally {
          controller.close();
        }
      },
    });

    return new Response(readable, {
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Error interno del servidor';
    return new Response(JSON.stringify({ error: message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
};
