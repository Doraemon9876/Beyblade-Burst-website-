const TOTAL_EPISODES = 231;

const video = document.getElementById("videoPlayer");
const statusBox = document.getElementById("status");

const currentEpisodeText =
    document.getElementById("currentEpisode");

const previousBtn =
    document.getElementById("previousBtn");

const nextBtn =
    document.getElementById("nextBtn");

const continueBtn =
    document.getElementById("continueBtn");

const autoNext =
    document.getElementById("autoNext");

const searchBox =
    document.getElementById("searchBox");

const episodeList =
    document.getElementById("episodeList");


let currentEpisode = 1;


/* -----------------------------------
   API helper
----------------------------------- */

async function api(url) {

    const response = await fetch(url, {
        cache: "no-store"
    });

    if (!response.ok) {
        throw new Error(
            `API error ${response.status}`
        );
    }

    return await response.json();
}


/* -----------------------------------
   Episode information
----------------------------------- */

async function loadEpisodeInfo(ep) {

    try {

        statusBox.textContent =
            `Loading Episode ${ep}...`;

        const data =
            await api(`/api/episode/${ep}`);

        console.log("Episode information:", data);

        return data;

    } catch (error) {

        console.error(error);

        statusBox.textContent =
            "Could not load episode information.";

        throw error;
    }
}


/* -----------------------------------
   Play episode
----------------------------------- */

async function playEpisode(ep, autoplay = false) {

    if (ep < 1 || ep > TOTAL_EPISODES) {
        return;
    }

    currentEpisode = ep;

    currentEpisodeText.textContent =
        `Episode ${ep}`;

    previousBtn.disabled =
        ep === 1;

    nextBtn.disabled =
        ep === TOTAL_EPISODES;


    try {

        const info =
            await loadEpisodeInfo(ep);

        console.log(
            `Playing episode ${ep}`,
            info
        );


        statusBox.textContent =
            `Loading Episode ${ep}...`;


        /*
         * Stop the previous video.
         */

        video.pause();

        video.removeAttribute("src");

        video.load();


        /*
         * Clean video URL (Allows byte-range seeking & caching)
         */

        const videoUrl = `/api/video/${ep}`;

        video.src = videoUrl;

        video.load();


        /*
         * Remember the last episode.
         */

        localStorage.setItem(
            "beybladeEpisode",
            String(ep)
        );


        if (autoplay) {

            try {

                await video.play();

            } catch (error) {

                console.log(
                    "Autoplay was blocked:",
                    error
                );

            }

        }


        statusBox.textContent =
            `Episode ${ep}: ${info.name}`;

    } catch (error) {

        console.error(
            "Episode loading failed:",
            error
        );

        statusBox.textContent =
            `Failed to load Episode ${ep}.`;

    }

    updateEpisodeHighlight();
}


/* -----------------------------------
   Previous
----------------------------------- */

previousBtn.addEventListener(
    "click",
    () => {

        if (currentEpisode > 1) {

            playEpisode(
                currentEpisode - 1,
                true
            );

        }

    }
);


/* -----------------------------------
   Next
----------------------------------- */

nextBtn.addEventListener(
    "click",
    () => {

        if (currentEpisode < TOTAL_EPISODES) {

            playEpisode(
                currentEpisode + 1,
                true
            );

        }

    }
);


/* -----------------------------------
   Auto Next
----------------------------------- */

video.addEventListener(
    "ended",
    () => {

        if (
            autoNext.checked &&
            currentEpisode < TOTAL_EPISODES
        ) {

            playEpisode(
                currentEpisode + 1,
                true
            );

        }

    }
);


/* -----------------------------------
   Video events
----------------------------------- */

video.addEventListener(
    "loadstart",
    () => {

        statusBox.textContent =
            `Loading Episode ${currentEpisode}...`;

    }
);


video.addEventListener(
    "canplay",
    () => {

        statusBox.textContent =
            `Episode ${currentEpisode} ready`;

    }
);


video.addEventListener(
    "waiting",
    () => {

        statusBox.textContent =
            "Buffering...";

    }
);


video.addEventListener(
    "playing",
    () => {

        statusBox.textContent =
            `Playing Episode ${currentEpisode}`;

    }
);


video.addEventListener(
    "error",
    () => {

        console.error(
            "Video error:",
            video.error
        );

        statusBox.textContent =
            "Video could not be played.";

    }
);


/* -----------------------------------
   Continue button
----------------------------------- */

continueBtn.addEventListener(
    "click",
    () => {

        const saved =
            Number(
                localStorage.getItem(
                    "beybladeEpisode"
                )
            );

        const ep =
            saved >= 1 &&
            saved <= TOTAL_EPISODES
                ? saved
                : 1;

        playEpisode(
            ep,
            true
        );

        video.scrollIntoView({
            behavior: "smooth",
            block: "center"
        });

    }
);


/* -----------------------------------
   Create episode list
----------------------------------- */

function createEpisodeList() {

    episodeList.innerHTML = "";

    for (
        let ep = 1;
        ep <= TOTAL_EPISODES;
        ep++
    ) {

        const button =
            document.createElement("button");

        button.className =
            "episode-button";

        button.dataset.episode =
            String(ep);

        button.textContent =
            `Episode ${ep}`;

        button.addEventListener(
            "click",
            () => {

                playEpisode(
                    ep,
                    true
                );

                window.scrollTo({
                    top: 0,
                    behavior: "smooth"
                });

            }
        );

        episodeList.appendChild(button);
    }

    updateEpisodeHighlight();
}


/* -----------------------------------
   Highlight current episode
----------------------------------- */

function updateEpisodeHighlight() {

    const buttons =
        document.querySelectorAll(
            ".episode-button"
        );

    buttons.forEach(button => {

        const ep =
            Number(button.dataset.episode);

        if (ep === currentEpisode) {

            button.classList.add("active");

        } else {

            button.classList.remove("active");

        }

    });
}


/* -----------------------------------
   Search
----------------------------------- */

searchBox.addEventListener(
    "input",
    () => {

        const query =
            searchBox.value
                .trim()
                .toLowerCase();

        const buttons =
            document.querySelectorAll(
                ".episode-button"
            );

        buttons.forEach(button => {

            const text =
                button.textContent.toLowerCase();

            button.style.display =
                text.includes(query)
                    ? "block"
                    : "none";

        });

    }
);


/* -----------------------------------
   Start
----------------------------------- */

createEpisodeList();

const savedEpisode =
    Number(
        localStorage.getItem(
            "beybladeEpisode"
        )
    );

if (
    savedEpisode >= 1 &&
    savedEpisode <= TOTAL_EPISODES
) {

    currentEpisode =
        savedEpisode;

    currentEpisodeText.textContent =
        `Episode ${savedEpisode}`;

}

updateEpisodeHighlight();
