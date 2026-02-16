![wtffmpeg](https://scottvr.github.io/images/wtff.png)

## TL;DR: Nearly-breaking changes to some command-line options. 
- *A snapshot of v0.1.0 was tagged as 'alpha' from the main branch, if you really want the old hacky behaviot** 

- If you previously used `wtff "some prompt"`: that still works, but now it **preloads context and then drops you into the REPL** instead of exiting immediately. If you truly want a single-shot, non-interactive invocation, there is a flag for that (see below).

---

## WTF is this? `ffmpeg`?

`wtffmpeg` is a command-line tool that uses a Large Language Model (LLM) to translate plain-English descriptions of video or audio tasks into **actual, executable `ffmpeg` commands**.

It is intended to eliminate a common workflow where you:

1. Search Stack Overflow
2. Read a 1000-word explanation
3. Copy/paste/typo, possibly misunderstand one or more conflicting amswers
5. Read help/usage because the Internet strangers only got you very close to what you want to do.
6. Repeat. (And repeat the entire workflow the next time you need to do something new.)

Instead, `wtffmpeg` lets you say what you want, review the generated command, optionally edit it, and then decide whether to run it.

The command is the point. The REPL was intended as an **assisted cli explorer**, not just a **one-shot command guesser with a cheat sheet**. The importance of conversation history (one-sided as it may be, since wtffmpeg does not by default display anything beyond the suggested `ffmpeg` command) **should not be underestimated**; being able to do someyhing like 
```
wtffmpeg> ok now just like that,
but have it create chapters in the
video container, using points when
audio is below some threshold for
more than 100 milliseconds"
```
and to have the LLM know what "just like that" means, because it knows what command you are referring to, is quite powerful. 

The truth is, that even as a capable long-time user of ffmpeg, even when I have historically arrived at very complicated ffmpeg command-lines or piped-together chains of commands, or long batches of them interspersed throughout bash logic, there are very few things I get right every tiime. 

## some more dead-horsing about the UI and defending the LLM use case

Often, complex `ffmpeg` usage is  very much a process of running many different *almost right* commands, and altering the input options and varying flags until arriving at one or more commands that will no doubt be preserved in text documents or shell scripts for the user to refer to later so that what is learned can be recalled, leading to long-term progress toward `ffmpeg` mastery. 

Prior to **wtffmpeg**, it was typical for me to spend a lot of time learning how (and *how not*) to accomplish some specific task with ffmpeg, and then *never* need to do that exact thing again, so..?

So, if I am honest, I will admit that *every* `ffmpeg` session that accomplishes anything useful or meaningful is already an exercise in up-arrow, command-history editing, and evolving incremental command-line mutations until finally one adaptation naturally selects to reproduce and pass on hard-won progress to the next generation of command.  Or something like it anyway.  

So... if I acknowledge that as the truth, then using a **etffmpeg** as a REPL for `ffmpeg` that is actually very often *at least as correct* the first time as I would have been  going it alone - and with search engines being a continually decreasing return on investment of our time, while inexplicably we continue to go back in hopes that search enshittification is over and...

Let's be intellectually  honest: the LLMs are at least *close to correct* about as often as I am. `ffmpeg` usage, for me, is already very non-deterministic. 
ffmpeg is just enormously powerful, and its list of capabilities and ways to affect their outcome is immense.

**wtffmpeg** is an auxillary tool for *using* ffmpeg. The ability of your command history and your knowledge to couple directly in a command-line interface, while the model's responses are shaped and improved throughout your experimentation session of discoveries actually makes this silly thing that I initially made as a joke into something I now have an obligation to improve and maintain because,..

**whether you disapprove of  it on moral grounds or not**, and you can be offended by it on intellectual grounds if you care to be, the fact is that **"ffmpeg cli configurator and experimental command lab assistant"** is a perfect use case for LLMs.

## CLI optional arguments
```
usage: wtff [options] [prompt]

--model MODEL           Model to use
--api-key KEY           OpenAI API key
--bearer-token TOKEN    Bearer token for compatible APIs
--url URL               Base API URL (OpenAI-compatible)
--prompt-once           Single-shot, non-interactive mode
--context-turns N       Number of turns of context to retain
-x, -e, --exec          Execute without confirmation
-c, --copy              Copy command to clipboard
```

There's stil a few to document and a few others I haven't gotten around to implementing yet.

The old `-i` flag is accepted but ignored. Interactive is the default now.

----

### Inside the REPL 
Lines starting with ! are executed as shell commands:
```
!ls -lh
!ffprobe input.mp4
```

These are just for convenience. You cannot, for example, `!chdir` and actually change your REPL process dir. (Though convenient `/cd` (slash commands) may be a thing soon.)

### A note about system prompts

I initially shipped `wtffmpeg` as a tiny REPL app with a huge system prompt that was arguably more valuable as a cheat sheet than as a generalizable input prompt for LLMs to "be good at ffmpeg".

By default it used Phi (locally)  and then slowly and inadvertantly through trial and error, I  arrived at system prompt as a necessary artifact of model capability constraints, and that served essentially as *finetuning by transcript*. Because doing so was simultaneously ludicrous and actually undeniably useful, I disclaimed `wtffmpeg` as "performance art".

As wtffmpeg continues to improve as it is in active development, that big ol' cheat sheet of a system prompt could actually be a hindrance when using a SoTA model. This is why it is being retired to a profile labeled "cheatsheet' in the next release, along with a handful of other profiles enabled by the new `--profile <list>`, where <list> is a plain-text file pointed to by an avsolute path, or a "profile name" if you want to use a profile from youe wtffmpeg profile directory. Anyway, some (even the v0.1.0 Phi-tailored joke) are shipped in the repo, but in the end it's just text, so you are free to use whatever you choose.


## Usage/Examples

```bash
$ wtff "convert test_pattern.mp4 to a gif"

--- Generated ffmpeg command ---
ffmpeg -i test_pattern.mp4 -vf "fps=10,scale=320:-1:flags=lanczos" output.gif
-------------------------------
Execute? [y/N], (c)opy to clipboard:
```

If you say y, it runs.
If you say c, it copies.
If you say anything else, nothing happens. You stay in the REPL. 

Running
```
wtff
```
drops you into an interactive session where importantly:
- Up/down arrow history browsing works.
- Left/right editing works.
- Prompt history is persisted to ~/.wtff_history.
- Each turn builds conversational context unless you tell it not to.

This is the intended interface.

----

Some people seem to prefer sending their first return stroke to the LLM at the time of command invocation. I don't know why, but to preserve their workflow, you can one-shot your request the way many people seem to do today, which is like:

```
wtff "turn this directory of PNGs into an mp4 slideshow"
```
This works, but it is essentially  just "preloading your first request to the LLM. You are still dropped into the REPL workflow.

If you really want single-shot, stateless execution, you can pass `--prompt-once`:
```
wtff --prompt-once "extract the audio from lecture.mp4"
```

This does not retain context. It generates once, then:

- prints the command
- optionally copies it
- optionally executes it
- exits

This is intentionally boring and predictable.

----

By default wtffmpeg's REPL retains conversational context, so that the LLM the **wtffmpeg** makes use of, is aware of each request (as well as command history) prior to the one presently being evaluated, but you can control or even disable that:

```
wtff --context-turns N
```
where N is a number greater than or equal to zero that represents the number of conversational turns you'd like to keep in context, with 0 effectively making the REPL stateless, and higher numbers  imdicating a greater number of pairs of prompt/response (as well as growing to eat more RAM, tokens, etc, and eventually bringing your LLM to a point of struggling to appear coherent, but you are free to set this to whatever number is best for you. It defaults to 12.

## Installation
Just do this:
```
git clone https://github.com/scottvr/wtffmpeg.git
cd wtffmpeg
pip install -e .
```

or use pipx, if that's your preference. Or even `uv pip install` if you like. But really, this just works and is the suggested method.

On this topic...  I have removed some earlier README changes that were sent to me by PR from a GitHub user. The PR added some steps about using `uv` and manually creating a `wtff` symlink somewhere in your PATH.  It was unnecessary from the start, but I was happy to see that others were taking an interest in **wtffmpeg** and if the additional steps in the README were helpful to that user, maybe they'd be helpful to others. So, rather than ask them what problem they were trying to solve with the PR, and point out that the steps were redundant, I was lazy. Besides, I considered that perhaps the PR  submitter was ome of the students I had read about somewhere that are required to "get a PR approved by an Open Source project" as part of coursework, and found the idea that **wtffmpeg** could help with that a pleasant idea, So lazy *and* generous! :-) 

In any case, now that this project has gotten much more attention that I expected, and I have since refactored the single script into multiple modules, the "uv, and "copy or symlink" steps are invalid now. (**btw, if you had installed the v0.1.0 code using *any* method, and especially if you used `-e` and install a new version before uninstalling 0.1.0, the autogenerated `wtff` stub can give errors because it will point to a `main()` entry point that no longer exists. please manually delete the `wtff` in your `bin` or `scripts` directory and then (re-)install **wtffmpeg**.) 

The reason I bring all this up is to say that absolutely I will accept contributions from the community, but please open an Issue if something doesnt work for you.

Which brings me to a PR submitted from another user fork: OpenAI API support, and exposing the configuration thereof via env:

## Configuration

### Environment Variables.
These were graciously implemented by someone in the community. Thanks.

- WTFFMPEG_MODEL: You can (but don't have to) specify a model name here. e.g, llama3, gpt-4o, codellama:7b
- WTFFMPEG_LLM_API_URL: Base URL for a local or remote OpenAI-compatible API
Defaults to http://localhost:11434 (Ollama)
- WTFFMPEG_OPENAI_API_KEY: What else would this be? :-)
- WTFFMPEG_BEARER_TOKEN: Bearer token for other OpenAI-compatible services.

### Add something about /slash ops
Later.

# Disclaimer
`wtffmpeg` started as something I built to amuse myself. It accidentally turned out to be useful.

It executes commands that can destroy your data if you are careless.
Always review generated commands before running them.

YMMV. Use at your own risk. I assume you know what ffmpeg can do.
