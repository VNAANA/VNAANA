"""The algorithm playground: a window to try the "For you" algorithm by hand.

Screen 1 is a mock onboarding (consent and interests). Screen 2 is the
playground: a feed of mock articles you can like, dislike, share and read,
your tag scores, an action log, and a clock you can move forward and back.
Every "?" explains the part next to it, with the live numbers.

Run it from the VNAANA root folder:

    python -m Backend.Testing_ENV.playground

No database or .env needed: everything lives in memory. The algorithm that
runs is the real one from Backend/Logic, through its normal ports.
"""

import tkinter as tk
import uuid
from datetime import timedelta
from tkinter import messagebox

from Backend.Logic.Algorithm.decay import LIFETIME_DAYS
from Backend.Logic.algorithm_service import AlgorithmService
from Backend.Logic.domain.feed import Feed, FeedStatus
from Backend.Logic.domain.story import Story
from Backend.Logic.domain.story_reaction import Reaction
from Backend.Testing_ENV.explain import (
    HELP,
    HOW_IT_WORKS,
    article_breakdown,
    day_of,
    number,
    tag_breakdown,
    unlock_summary,
)
from Backend.Testing_ENV.mock_data import TAGS
from Backend.Testing_ENV.playground_repository import (
    Action,
    ActionKind,
    PlaygroundAlgorithmRepository,
    PlaygroundUserRepository,
    World,
)

# ---- look ------------------------------------------------------------------------------

BACKGROUND = "#f4f5f7"
PANEL = "#ffffff"
BORDER = "#dfe1e6"
TEXT = "#1f2328"
MUTED = "#6b7280"
ACCENT = "#2563eb"
POSITIVE = "#16a34a"
NEGATIVE = "#dc2626"
LIKED = "#dcfce7"
DISLIKED = "#fee2e2"
BUTTON = "#eef0f3"

FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 16, "bold")
FONT_HEADER = ("Segoe UI", 12, "bold")

ACTION_LABELS = {
    ActionKind.like: "Liked",
    ActionKind.dislike: "Disliked",
    ActionKind.clear_reaction: "Removed reaction on",
    ActionKind.share: "Shared",
    ActionKind.read: "Read to the end",
}


# ---- small building blocks -----------------------------------------------------------------

def show_info(parent: tk.Misc, title: str, text: str) -> None:
    """A small popup with an explanation."""
    popup = tk.Toplevel(parent, bg=PANEL)
    popup.title(title)
    popup.transient(parent.winfo_toplevel())
    popup.resizable(True, True)

    tk.Label(popup, text=title, font=FONT_HEADER, bg=PANEL, fg=TEXT, anchor="w").pack(
        fill="x", padx=16, pady=(14, 6)
    )

    width = 80
    lines = sum(len(line) // width + 1 for line in text.split("\n"))
    body = tk.Text(
        popup, wrap="word", font=FONT, bg=PANEL, fg=TEXT, relief="flat",
        width=width, height=min(max(lines, 5), 32), padx=4, pady=4,
    )
    body.insert("1.0", text)
    body.configure(state="disabled")
    body.pack(fill="both", expand=True, padx=12)

    tk.Button(popup, text="Close", command=popup.destroy, font=FONT, bg=BUTTON, relief="flat",
              padx=14, pady=4, cursor="hand2").pack(pady=12)
    popup.bind("<Escape>", lambda _event: popup.destroy())

    # Open in the middle of the main window instead of wherever the OS puts it.
    owner = parent.winfo_toplevel()
    popup.update_idletasks()
    x = owner.winfo_rootx() + (owner.winfo_width() - popup.winfo_reqwidth()) // 2
    y = owner.winfo_rooty() + (owner.winfo_height() - popup.winfo_reqheight()) // 3
    popup.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    popup.focus_set()


def help_button(parent: tk.Misc, key: str, bg: str = PANEL) -> tk.Button:
    """A "?" that opens one of the fixed explanations."""
    title, text = HELP[key]
    return question_mark(parent, lambda: show_info(parent, title, text), bg)


def question_mark(parent: tk.Misc, command, bg: str = PANEL) -> tk.Button:
    return tk.Button(
        parent, text="?", command=command, font=FONT_BOLD, fg=ACCENT, bg=bg,
        activeforeground=ACCENT, relief="flat", bd=0, padx=4, cursor="hand2",
    )


def clear(frame: tk.Misc) -> None:
    for child in frame.winfo_children():
        child.destroy()


class ScrollFrame(tk.Frame):
    """A frame with a vertical scrollbar; put widgets in `.inner`."""

    def __init__(self, parent: tk.Misc, bg: str = PANEL) -> None:
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)

        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(window, width=e.width))
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Scroll with the mouse wheel only while the pointer is above this frame.
        self.canvas.bind("<Enter>", lambda _e: self._wheel(True))
        self.canvas.bind("<Leave>", lambda _e: self._wheel(False))

    def _wheel(self, on: bool) -> None:
        if on:
            self.canvas.bind_all("<MouseWheel>", self._on_wheel)                                   # Windows, macOS
            self.canvas.bind_all("<Button-4>", lambda _e: self.canvas.yview_scroll(-1, "units"))  # Linux
            self.canvas.bind_all("<Button-5>", lambda _e: self.canvas.yview_scroll(1, "units"))
        else:
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.canvas.unbind_all(sequence)

    def _on_wheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def to_top(self) -> None:
        self.canvas.yview_moveto(0)


def panel(parent: tk.Misc, title: str, help_key: str) -> tuple[tk.Frame, tk.Frame]:
    """A white box with a header and a "?"; returns (box, header)."""
    box = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    header = tk.Frame(box, bg=PANEL)
    header.pack(fill="x", padx=12, pady=(10, 4))
    tk.Label(header, text=title, font=FONT_HEADER, bg=PANEL, fg=TEXT).pack(side="left")
    help_button(header, help_key).pack(side="left", padx=(4, 0))
    return box, header


# ---- the app --------------------------------------------------------------------------------

class PlaygroundApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("VNAANA algorithm playground")
        self.geometry("1400x820")
        self.minsize(1150, 650)
        self.configure(bg=BACKGROUND)

        self.world = World()
        self.service = AlgorithmService(
            PlaygroundAlgorithmRepository(self.world),
            PlaygroundUserRepository(self.world),
        )

        self.last_picks: list[str] = []
        self.last_consent = True

        self.screen = tk.Frame(self, bg=BACKGROUND)
        self.screen.pack(fill="both", expand=True)
        self.show_onboarding()

    # ==== screen 1: onboarding ==================================================================

    def show_onboarding(self) -> None:
        clear(self.screen)

        card = tk.Frame(self.screen, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        card.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(card, text="Welcome to VNAANA", font=FONT_TITLE, bg=PANEL, fg=TEXT).pack(
            anchor="w", padx=28, pady=(24, 2)
        )
        tk.Label(
            card, bg=PANEL, fg=MUTED, font=FONT, justify="left", wraplength=520,
            text="This is a mock onboarding. What you choose here is what a new user "
                 "would choose in the app. After this you can play with the feed and "
                 "watch the algorithm react.",
        ).pack(anchor="w", padx=28, pady=(0, 18))

        # consent first, then interests
        consent = tk.BooleanVar(value=self.last_consent)
        row = tk.Frame(card, bg=PANEL)
        row.pack(anchor="w", padx=28)
        tk.Checkbutton(
            row, text="I allow VNAANA to use what I do to personalise my news",
            variable=consent, font=FONT, bg=PANEL, activebackground=PANEL, cursor="hand2",
        ).pack(side="left")
        help_button(row, "consent").pack(side="left")

        row = tk.Frame(card, bg=PANEL)
        row.pack(anchor="w", padx=28, pady=(18, 4))
        tk.Label(row, text="What are you interested in?", font=FONT_BOLD, bg=PANEL, fg=TEXT).pack(side="left")
        help_button(row, "interests").pack(side="left")

        grid = tk.Frame(card, bg=PANEL)
        grid.pack(anchor="w", padx=36)
        picks = {name: tk.BooleanVar(value=name in self.last_picks) for name in TAGS}
        for index, name in enumerate(TAGS):
            tk.Checkbutton(
                grid, text=name, variable=picks[name], font=FONT, bg=PANEL,
                activebackground=PANEL, cursor="hand2", width=16, anchor="w",
            ).grid(row=index % 5, column=index // 5, sticky="w", pady=1)

        tk.Label(
            card, bg=PANEL, fg=MUTED, font=FONT_SMALL, justify="left", wraplength=520,
            text="Tip: pick nothing to see what happens to a user who skips onboarding.",
        ).pack(anchor="w", padx=28, pady=(10, 0))

        def start() -> None:
            self.last_picks = [name for name in TAGS if picks[name].get()]
            self.last_consent = consent.get()
            self.world.onboard(self.last_picks, consent=self.last_consent)
            self.show_playground()

        tk.Button(
            card, text="Start", command=start, font=FONT_BOLD, bg=ACCENT, fg="white",
            activebackground=ACCENT, activeforeground="white", relief="flat",
            padx=28, pady=6, cursor="hand2",
        ).pack(anchor="e", padx=28, pady=(18, 24))

    # ==== screen 2: the playground ==============================================================

    def show_playground(self) -> None:
        clear(self.screen)

        # ---- top bar ----
        bar = tk.Frame(self.screen, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        bar.pack(fill="x")

        tk.Button(
            bar, text="← Back to onboarding", command=self.back_to_onboarding, font=FONT,
            bg=BUTTON, relief="flat", padx=10, pady=4, cursor="hand2",
        ).pack(side="left", padx=(12, 20), pady=8)

        for label, days in (("−7", -7), ("−1", -1)):
            self.time_button(bar, label, days).pack(side="left", padx=2)
        self.day_label = tk.Label(bar, font=FONT_HEADER, bg=PANEL, fg=TEXT, width=8)
        self.day_label.pack(side="left", padx=6)
        for label, days in (("+1", 1), ("+7", 7)):
            self.time_button(bar, label, days).pack(side="left", padx=2)
        help_button(bar, "time").pack(side="left", padx=(4, 24))

        self.status_label = tk.Label(bar, font=FONT_BOLD, bg=PANEL)
        self.status_label.pack(side="left")
        question_mark(bar, self.explain_status).pack(side="left", padx=(4, 0))

        tk.Button(
            bar, text="How it works", command=lambda: show_info(self, "How it works", HOW_IT_WORKS),
            font=FONT_BOLD, bg=ACCENT, fg="white", activebackground=ACCENT, activeforeground="white",
            relief="flat", padx=14, pady=4, cursor="hand2",
        ).pack(side="right", padx=12)

        # ---- three columns: feed | tag scores | action log ----
        body = tk.Frame(self.screen, bg=BACKGROUND)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        # Fixed widths for the two side panels, the feed takes the rest.
        log_box, _ = panel(body, "Action log", "action_log")
        log_box.configure(width=270)
        log_box.pack_propagate(False)
        log_box.pack(side="right", fill="y", padx=(12, 0))
        self.log_list = ScrollFrame(log_box)
        self.log_list.pack(fill="both", expand=True, padx=(8, 0), pady=(0, 8))

        tags_box, _ = panel(body, "Your tag scores", "tag_scores")
        tags_box.configure(width=330)
        tags_box.pack_propagate(False)
        tags_box.pack(side="right", fill="y", padx=(12, 0))
        self.tags_list = tk.Frame(tags_box, bg=PANEL)
        self.tags_list.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        feed_box, feed_header = panel(body, "Feed", "article_score")
        feed_box.pack(side="left", fill="both", expand=True)
        help_button(feed_header, "actions").pack(side="right")
        tk.Label(feed_header, text="What are Like / Dislike / Share / Read worth?", font=FONT_SMALL,
                 bg=PANEL, fg=MUTED).pack(side="right")
        self.feed_note = tk.Label(feed_box, font=FONT_SMALL, bg=PANEL, fg=MUTED, justify="left", anchor="w")
        self.feed_note.pack(fill="x", padx=12)
        feed_box.bind("<Configure>", lambda e: self.feed_note.configure(wraplength=max(e.width - 30, 200)))
        self.feed_list = ScrollFrame(feed_box)
        self.feed_list.pack(fill="both", expand=True, padx=(4, 0), pady=(4, 8))

        self.refresh()

    def time_button(self, parent: tk.Misc, label: str, days: int) -> tk.Button:
        return tk.Button(
            parent, text=label, command=lambda: self.move_clock(days), font=FONT_BOLD,
            bg=BUTTON, relief="flat", width=3, cursor="hand2",
        )

    # ---- what the buttons do ----

    def back_to_onboarding(self) -> None:
        if messagebox.askyesno(
            "Back to onboarding",
            "Start over with a new user? Everything you did in the playground is cleared.",
            parent=self,
        ):
            self.show_onboarding()

    def move_clock(self, days: int) -> None:
        self.world.set_day(self.world.day + days)
        self.refresh()

    def act(self, kind: ActionKind, story_id: uuid.UUID) -> None:
        # Tapping the active reaction again removes it, like in the app.
        current = self.world.reaction_on(story_id)
        if current is not None and kind.value == current.reaction.value:
            kind = ActionKind.clear_reaction

        if self.world.hidden_actions() and not messagebox.askyesno(
            "Change the past?",
            f"You are on day {self.world.day}, before {len(self.world.hidden_actions())} later "
            "action(s). Doing something now deletes those for good, like undo in an editor.\n\n"
            "Continue?",
            parent=self,
        ):
            return

        self.world.record(kind, story_id)
        self.refresh(keep_scroll=True)

    # ---- drawing everything ----

    def refresh(self, keep_scroll: bool = False) -> None:
        now = self.world.now

        # Same as the hourly job followed by a feed request in the API.
        self.service.run_scoring(now=now)
        feed = self.service.get_feed(self.world.user.id, limit=len(self.world.stories), now=now)

        self.day_label.configure(text=f"Day {self.world.day}")
        self.draw_status(feed)
        self.draw_feed(feed)
        self.draw_tags(feed)
        self.draw_log()

        if not keep_scroll:
            self.feed_list.to_top()

    def draw_status(self, feed: Feed) -> None:
        text, colour = {
            FeedStatus.available: ("For you: unlocked", POSITIVE),
            FeedStatus.locked: ("For you: locked, showing the general feed", "#b45309"),
            FeedStatus.no_consent: ("For you: off (no consent), showing the general feed", MUTED),
        }[feed.status]
        self.status_label.configure(text=text, fg=colour)
        self.feed_status = feed.status

    def explain_status(self) -> None:
        title, text = HELP["feed_status"]
        if self.feed_status == FeedStatus.no_consent:
            live = "Right now: you did not give consent, so the algorithm does not run for you."
        else:
            has_declared = bool(self.service.algorithm.list_declared_tags(self.world.user.id))
            live = "Right now:\n" + unlock_summary(self.world.stored_scores, has_declared_tags=has_declared)
        show_info(self, title, f"{text}\n\n{live}")

    def draw_feed(self, feed: Feed) -> None:
        clear(self.feed_list.inner)

        if feed.status == FeedStatus.available:
            rows = [(ranked.story, ranked.score) for ranked in feed.stories]
            self.feed_note.configure(text="Your personal feed, highest score first. Click a score's ? to see why.")
        else:
            # The general feed: newest first, nobody's scores involved.
            since = self.world.now - timedelta(days=LIFETIME_DAYS)
            stories = self.service.algorithm.list_candidate_stories(since)
            rows = [(story, None) for story in sorted(stories, key=lambda s: s.last_updated_at, reverse=True)]
            self.feed_note.configure(
                text="The general feed, newest first: the same for everyone. "
                + ("Like, share or read articles to unlock \"For you\"."
                   if feed.status == FeedStatus.locked else
                   "Without consent your actions are not tracked, so the buttons are off.")
            )

        if not rows:
            tk.Label(
                self.feed_list.inner, bg=PANEL, fg=MUTED, font=FONT, justify="left",
                text=f"No articles. Every article is removed {LIFETIME_DAYS} days after it was published.",
            ).pack(anchor="w", padx=12, pady=12)

        tracking = feed.status != FeedStatus.no_consent
        for position, (story, score) in enumerate(rows, start=1):
            self.draw_article(position, story, score, tracking)

    def draw_article(self, position: int, story: Story, score: float | None, tracking: bool) -> None:
        reaction = self.world.reaction_on(story.id)
        bg = PANEL
        if reaction is not None:
            bg = LIKED if reaction.reaction == Reaction.like else DISLIKED

        row = tk.Frame(self.feed_list.inner, bg=bg, highlightbackground=BORDER, highlightthickness=1)
        row.pack(fill="x", padx=8, pady=4)

        top = tk.Frame(row, bg=bg)
        top.pack(fill="x", padx=10, pady=(8, 0))
        tk.Label(top, text=f"{position}.", font=FONT_BOLD, bg=bg, fg=MUTED, width=3, anchor="w").pack(side="left")
        tk.Label(top, text=story.title, font=FONT_BOLD, bg=bg, fg=TEXT, anchor="w").pack(side="left")

        if score is not None:
            colour = POSITIVE if score > 0 else NEGATIVE if score < 0 else MUTED
            question_mark(top, lambda: self.explain_article(story.id), bg).pack(side="right")
            tk.Label(top, text=number(score), font=FONT_BOLD, bg=bg, fg=colour).pack(side="right")
            tk.Label(top, text="score", font=FONT_SMALL, bg=bg, fg=MUTED).pack(side="right", padx=(0, 4))

        published = day_of(story.last_updated_at)
        age = self.world.day - published
        age_text = "published today" if age == 0 else f"published day {published}, {age} day{'s' * (age != 1)} old"
        tags = ", ".join(self.world.tag_names_of(story.id))
        tk.Label(row, text=f"{tags}   ·   {age_text}", font=FONT_SMALL, bg=bg, fg=ACCENT, anchor="w").pack(
            fill="x", padx=(40, 10)
        )
        tk.Label(row, text=story.summary, font=FONT_SMALL, bg=bg, fg=MUTED, anchor="w", justify="left",
                 wraplength=640).pack(fill="x", padx=(40, 10))

        buttons = tk.Frame(row, bg=bg)
        buttons.pack(anchor="w", padx=(38, 10), pady=(4, 8))
        state = "normal" if tracking else "disabled"
        current = reaction.reaction if reaction is not None else None

        for kind, label, active in (
            (ActionKind.like, "Like", current == Reaction.like),
            (ActionKind.dislike, "Dislike", current == Reaction.dislike),
            (ActionKind.share, "Share", False),
            (ActionKind.read, "Read", False),
        ):
            colour = (POSITIVE if kind == ActionKind.like else NEGATIVE) if active else BUTTON
            tk.Button(
                buttons, text=label, state=state, font=FONT_BOLD if active else FONT,
                bg=colour, fg="white" if active else TEXT, relief="flat", padx=10, pady=1,
                cursor="hand2", command=lambda k=kind: self.act(k, story.id),
            ).pack(side="left", padx=(0, 6))

    def explain_article(self, story_id: uuid.UUID) -> None:
        breakdown = article_breakdown(self.world, story_id, self.world.stored_scores)
        show_info(self, f"Why \"{breakdown.title}\" has this score", breakdown.as_text())

    def draw_tags(self, feed: Feed) -> None:
        clear(self.tags_list)

        if feed.status == FeedStatus.no_consent:
            tk.Label(self.tags_list, text="No consent: nothing is scored.", font=FONT, bg=PANEL,
                     fg=MUTED, anchor="w").pack(anchor="w")
            return

        scores = self.world.stored_scores
        biggest = max([abs(score) for score in scores.values()] + [1.0])
        ordered = sorted(self.world.tag_ids.items(), key=lambda item: scores.get(item[1], 0.0), reverse=True)

        for name, tag_id in ordered:
            score = scores.get(tag_id, 0.0)
            row = tk.Frame(self.tags_list, bg=PANEL)
            row.pack(fill="x", pady=3)

            tk.Label(row, text=name, font=FONT, bg=PANEL, fg=TEXT, width=13, anchor="w").pack(side="left")

            bar = tk.Canvas(row, width=110, height=14, bg=PANEL, highlightthickness=0)
            bar.pack(side="left")
            middle = 55
            bar.create_line(middle, 0, middle, 14, fill=BORDER)
            length = 54 * abs(score) / biggest
            if score > 0:
                bar.create_rectangle(middle, 2, middle + length, 12, fill=POSITIVE, width=0)
            elif score < 0:
                bar.create_rectangle(middle - length, 2, middle, 12, fill=NEGATIVE, width=0)

            colour = POSITIVE if score > 0 else NEGATIVE if score < 0 else MUTED
            tk.Label(row, text=number(score), font=FONT_BOLD, bg=PANEL, fg=colour, width=6, anchor="e").pack(side="left")
            question_mark(row, lambda t=tag_id: self.explain_tag(t)).pack(side="left")

        tk.Label(
            self.tags_list, bg=PANEL, fg=MUTED, font=FONT_SMALL, justify="left", wraplength=290,
            text="\nGreen bars: tags you like. Red bars: tags you don't. "
                 "Click a ? to see which actions built the score.",
        ).pack(anchor="w")

    def explain_tag(self, tag_id: uuid.UUID) -> None:
        breakdown = tag_breakdown(self.world, tag_id)
        show_info(self, f"How your {breakdown.tag} score is built", breakdown.as_text())

    def draw_log(self) -> None:
        clear(self.log_list.inner)
        visible = self.world.visible_actions()
        hidden = self.world.hidden_actions()

        if hidden:
            tk.Label(
                self.log_list.inner, bg=PANEL, fg=MUTED, font=FONT_SMALL, justify="left", wraplength=220,
                text=f"{len(hidden)} later action(s) are undone for now. "
                     "Move forward to bring them back.",
            ).pack(anchor="w", padx=4, pady=(0, 6))

        if not visible and not hidden:
            tk.Label(self.log_list.inner, text="Nothing yet.", font=FONT_SMALL, bg=PANEL,
                     fg=MUTED).pack(anchor="w", padx=4)

        for action in visible + hidden:
            undone = action in hidden
            tk.Label(
                self.log_list.inner, text=self.describe(action), font=FONT_SMALL, bg=PANEL,
                fg="#a3a8b0" if undone else TEXT, justify="left", anchor="w", wraplength=220,
            ).pack(fill="x", anchor="w", padx=4, pady=2)

    def describe(self, action: Action) -> str:
        day = f"Day {day_of(action.at)}"
        if action.kind == ActionKind.declare:
            return f"{day}   Picked {self.world.tag_names[action.tag_id]}"
        title = self.world.articles[action.story_id].title
        return f"{day}   {ACTION_LABELS[action.kind]} \"{title}\""


def main() -> None:
    PlaygroundApp().mainloop()


if __name__ == "__main__":
    main()
