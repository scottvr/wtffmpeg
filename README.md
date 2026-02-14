# wtffmpeg - natural language to ffmpeg
without the chat UI inconvenience

## TL;DR (breaking CLI change, but the good kind)
A snapshot of v0.1.0 was tagged as 'alpha' from the main branch. If you don't want to switch to the current (as of Feb 2026) beta release, you can pull that 'alpha' tagged release, or download tarballs or zips of it from github.

- The old `-i` / “interactive mode” is now the **default**.
- Running `wtff` with no arguments drops you straight into a REPL.
- This is intentional. A command-line tool should behave like one.

If you previously used `wtff "some prompt"`: that still works, but now it **preloads context and then drops you into the REPL** instead of exiting immediately. If you truly want a single-shot, non-interactive invocation, there is a flag for that (see below).

---

## WTF is this?

`wtffmpeg` is a command-line tool that uses a Large Language Model (LLM) to translate plain-English descriptions of video or audio tasks into **actual, executable `ffmpeg` commands**.

It exists to eliminate this workflow:

1. Search Stack Overflow
2. Read a 900-word explanation
3. Copy/paste a command
4. Fix three flags
5. Repeat. (And repeat the entire workflow the next time you need to do something new.)

Instead, you say what you want, review the generated command, optionally edit it, and then decide whether to run it.

The command is the point. The REPL was the intent. Truth is, that even as a capable long-time user of ffmpeg, even when I have historically arrived at very complicated ffmpeg command-lines or piped-together chains of commands, or long batches of them intersperse throughout bash logic, there are very few things I get right every tiime. 

ffmpeg usage is often very much a process of running many different *almost right* commands, and altering the input options and flags and varying them until arriving at one or more commands that will no doubt be preserved in text documents or shell scripts for the user to refer to later.

It is often the case that I will spend a lot of time learning how (and how not) to accomplish some specific thing , and then *never* need to do that exact thing again. 

So, if I am honest, I will admit that *every* ffmpeg session that accomplishes anything useful or meaningful, is already an exercise in up-arrow, command-history editing, and evolving mutating things you know how to accomplish, until you eventually arrive at a way to accomplish the thing you set out to do.  So, if I ackowledge that is true, then using a REPL for ffmpeg that is often correct, often nearly correct, "learning" and changing tactics throughout the process seems a natural fit.

ffmpeg usage, for me, is already very non-deterministic. ffmpeg is just enormously powerful, and its list of capabilities and ways to affect their outcome is immense.

`wtffmpeg` is an auxillary tool for *using* ffmpeg. The ability of your command history and your knowledge, to couple directly in a command-line interface, while the model's responses are shaped and improved throughout your experimental session, actually makes this thing I made as a joke  into something I now haave an obligation to improve and maintain because  - approve of  it on moral grounds or not, be offended by it on intellevtual grounds if you care to be -  but ffmpeg cli configurator and experimental command lab assistant is a perfect use case for an LLM.

I initially shipped `wwtffmpeg` as a tiny REPL app with a huge system prompt that was actual more valuable as a cheat sheet than a generalizable input for LLMs to "be good at ffmpeg".
It by default used Phi, and then slowly and inadvertantly through trial and error, I  arrived at system prompt was a necessary artifact of model capability constraints, and served essentially as *finetuning by transcript*. For a small local model. Because doing so was simultaneously ludicrous and undeniably useful.

With the updates to this branch, the default system prompt could likely be a hindrance to a SoTA model. This is why it is being retired to a profile labeled "cheatsheet' in this release, along with a handful of other profiles enabled by the new `--profile <list>`, where <list> is a plain-text file pointed to by an avsolute path, or a "profile name" if you want to use a profile from youe wtffmpeg profile directory. Anyway, some (een the v0.1.0 Phi-tailored joke of a prompt) are shipped in the repo, but in the end it's just text, so you are free to use whatever you choose.

---

## Examples

```bash
$ wtff "convert test_pattern.mp4 to a gif"

--- Generated ffmpeg command ---
ffmpeg -i test_pattern.mp4 -vf "fps=10,scale=320:-1:flags=lanczos" output.gif
-------------------------------
Execute? [y/N], (c)opy to clipboard:
```

If you say y, it runs.
If you say c, it copies.
If you say anything else, nothing happens.

You stay in the REPL. As I just stream-of-consciousnesseed a lot of words on  the topic of, it's ;iterally the point.

Running
```
wtff
```
It drops you into an interactive session where importantly:
- Up/down arrow history works.
- Left/right editing works.
- History is persisted to ~/.wtff_history.
- Each turn builds conversational context unless you tell it not to.

This is the intended interface.

----

Some people seem to prefer sending their first return stroke to the LLM at the time of command invocation. I don't know why, but to preserve their workflow, you can one-shot your request the way many people seem to do today, which is like:

```
wtff "turn this directory of PNGs into an mp4 slideshow"
```
This works, but it is essentially  just "preloading your first request to the LLM. You are still dropped into the hopefully now-pleasant REPL workflow.

If you really want single-shot, stateless execution, you can pass `--prompt-once`
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

By default wtffmpeg's REPL retains conversational context, as well as command history, but you can control or disable tthat.

```
wtff --context-turns N
```
where N is a number greater than or equal to zero that represents the number of conversational turns you'd like to keep in context, with 0 effectively making the REPL stateless, and higher numbers  imdicating a greater number of pairs of prompt/response (as well as growing to eat more RAM, tokens, etc, and eventually bringing your LLM to a point of struggling to appear coherent, but you are free to set this to whatever number is best for you. It defaults to 12.

## Installation
When random Internet users were clearly getting more excitement out of wtffmpeg than I was, I tended to accept PR's that were of little obvious value to me, but I accepted someone's initial OPENAI API integrations, and maybe more than one installation method I felt were unnecessary since it has had a pyproject.toml since day one and could be installed then with pip, pipx, or uv, and it would install a stub, in the bin or scripts directory of your system or venv Python path. One patch included a documentation change describing how to symlink wtffmpeg.py into a system path so you can access it by typing `wtff` from any command-line. That was literally a feature I shipped on day 1 via the `setuptools` innate scripts mechanism. But, as I said, these people were actually wanting to use wtffmpeg so who am I to deny them joy or explain that the feature was already there and documenteed? *shrug*

But after I'm now finding auto-generated LLM video slop (it's literally just a screenshot of a browser loading the wtffmpeg github repo browser render of README.md with a low-rent verion of a NotebookLM-style "podcast" for audio.  It's funny. And sad. But also someone wrote in a newsletter calling `scottvr/wtffmpeg` "Repo of the Week". A corporate marketing/tutorial video on how to use their synthetic data and partially-automated model/prompt pairing combination and pricing tool referred kindly to wtffmpeg, and kept a browser tab to the repo open throughout the video. (Sadly, he also showed the aforementioned silly-but-working-on-Phi prompt from wtffmpeg, and unsurprisingly ChatGPT could outperform the wtffmpeg joke-ish prompt with a system prompt that it wrote itself.) But also... and this *was* surprising: the maker of the video actually went out of his way to acknowledge that in some cases wtffmpeg's ludicrous prompt actually worked better! When tested using Phi. (LOL)

But I digress. Where were we? Oh yes, installation. Just do this:
```
git clone https://github.com/scottvr/wtffmpeg.git
cd wtffmpeg
pip install -e .
```

(or pipx, if that's your preference. Or `uv pip install` if you like. But really, this just works and doesn't need incremental changes to the process. Maybe I will package and toss it up on PyPi, once the modularization refactor is complete. But regardless, just `pip install` it from source, amd `wtff` command will just work without any symlinking or special installer support needed. That is to say, that I'm taking the project on again, at least for a bit, and hopefully you will all find it useful. If not, it is open source and you are free to fork it and shape it how you think it should be, but I might argue there are much better and more appropriate projects to fork a new project from, than one that was ludicrous architecture by design and intent, and yet was simultaneously actually useful and fun, while being the most polarizing thing I've ever done on the Internet at large. 

---

# Configuration

## Environment Variables.
These were graciously implemented by someone in the community. Thanks.

- WTFFMPEG_MODEL: You can (but don't have to) specify a model name here. e.g, llama3, gpt-4o, codellama:7b
- WTFFMPEG_LLM_API_URL: Base URL for a local or remote OpenAI-compatible API
Defaults to http://localhost:11434 (Ollama)
- WTFFMPEG_OPENAI_API_KEY: What else would this be? :-)
- WTFFMPEG_BEARER_TOKEN: Bearer token for other OpenAI-compatible services.

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

----

# Disclaimer
`wtffmpeg` started as something I built to amuse myself. It accidentally turned out to be useful.

It executes commands that can destroy your data if you are careless.
Always review generated commands before running them.

YMMV. Use at your own risk. I assume you know what ffmpeg can do.
