document.addEventListener('DOMContentLoaded', function () {
    const tg = window.Telegram.WebApp;
    tg.expand(); // Web ilovani to'liq ekranga yoyish

    const movieListElement = document.getElementById('movie-list');
    const searchInput = document.getElementById('search-input');
    let allMovies = [];

    // Ma'lumotlarni olish
    fetch('movies.json')
        .then(response => response.json())
        .then(data => {
            // Raqam bo'yicha saralash
            allMovies = Object.entries(data).sort((a, b) => parseInt(a[0]) - parseInt(b[0]));
            renderMovies(allMovies);
        })
        .catch(error => {
            console.error('Error fetching movies:', error);
            movieListElement.innerHTML = '<p style="color: #ff4d4d;">Kinolar roʻyxatini yuklashda xatolik yuz berdi.</p>';
        });

    function renderMovies(movies) {
        movieListElement.innerHTML = '';
        if (movies.length === 0) {
            movieListElement.innerHTML = '<p>Kinolar topilmadi.</p>';
            return;
        }
        movies.forEach(([number, fileId]) => {
            const item = document.createElement('div');
            item.className = 'movie-item';
            item.innerHTML = `<span class="movie-item-number">#${number}</span> Kino`; // Nomini keyinroq qo'shish mumkin
            item.onclick = () => {
                if (tg.initDataUnsafe.user) { // Faqat telegram ichida bosilsa
                    tg.sendData(number); // Botga kino raqamini yuborish
                }
            };
            movieListElement.appendChild(item);
        });
    }

    // Qidiruv
    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        const filteredMovies = allMovies.filter(([number, fileId]) => {
            return number.includes(searchTerm);
        });
        renderMovies(filteredMovies);
    });

});
