using System;
using System.Net.Http;
using System.Threading.Tasks;
using System.Collections.ObjectModel;
using TestMaui.Models;
using TestMaui.ViewModels;

namespace TestMaui.MVVM
{
    public partial class PlaylistsPage : ContentPage
    {
        private readonly HttpClient _httpClient;
        private readonly CircuitBreaker _circuitBreaker;

        public PlaylistsPage()
        {
            InitializeComponent();
            ViewModel = new PlaylistsViewModel(new PageService());
            _httpClient = new HttpClient();
            _circuitBreaker = new CircuitBreaker(3, TimeSpan.FromSeconds(10)); // 3 failures, 10-second reset timeout
        }

        protected override async void OnAppearing()
        {
            base.OnAppearing();
            await PerformNetworkRequestWithRetriesAsync();
        }

        void OnPlaylistSelected(object sender, SelectedItemChangedEventArgs e)
        {
            ViewModel.SelectPlaylistCommand.Execute(e.SelectedItem);
        }

        private PlaylistsViewModel ViewModel { get { return BindingContext as PlaylistsViewModel; } set { BindingContext = value; } }

        // Basic HTTP response checking
        private async Task PerformNetworkRequestAsync()
        {
            try
            {
                var response = await _httpClient.GetAsync("https://example.com/api/playlists");
                if (response.StatusCode == System.Net.HttpStatusCode.OK)
                {
                    Console.WriteLine("HTTP request succeeded");
                }
                else
                {
                    Console.WriteLine($"HTTP request failed with status code {response.StatusCode}");
                }
            }
            catch (HttpRequestException ex)
            {
                Console.WriteLine($"Network error: {ex.Message}");
            }
        }

        // Advanced: Retry with exponential backoff
        private async Task PerformNetworkRequestWithRetriesAsync()
        {
            int retries = 3;
            TimeSpan backoff = TimeSpan.FromSeconds(2);

            while (retries > 0)
            {
                try
                {
                    await PerformWithTimeoutAsync(PerformNetworkRequestAsync, TimeSpan.FromSeconds(5));
                    break; // Success, exit retry loop
                }
                catch (Exception ex)
                {
                    retries--;
                    Console.WriteLine($"Error: {ex.Message}. Retrying in {backoff.Seconds} seconds...");

                    if (retries > 0)
                    {
                        await Task.Delay(backoff);
                        backoff = backoff * 2; // Exponential backoff
                    }
                    else
                    {
                        Console.WriteLine("All retry attempts failed.");
                    }
                }
            }
        }

        // Advanced: Timeout mechanism
        private async Task PerformWithTimeoutAsync(Func<Task> operation, TimeSpan timeout)
        {
            using (var cts = new System.Threading.CancellationTokenSource(timeout))
            {
                var task = operation();
                var completedTask = await Task.WhenAny(task, Task.Delay(timeout, cts.Token));

                if (completedTask == task)
                {
                    await task; // If it was the original task, await it to propagate exceptions
                }
                else
                {
                    throw new TimeoutException("The operation timed out.");
                }
            }
        }
    }

    // Advanced: Circuit breaker mechanism
    public class CircuitBreaker
    {
        private int _failureCount = 0;
        private readonly int _failureThreshold;
        private readonly TimeSpan _resetTimeout;
        private DateTime _lastFailureTime;

        public CircuitBreaker(int failureThreshold, TimeSpan resetTimeout)
        {
            _failureThreshold = failureThreshold;
            _resetTimeout = resetTimeout;
        }

        public async Task CallAsync(Func<Task> operation)
        {
            if (_failureCount >= _failureThreshold && DateTime.UtcNow - _lastFailureTime < _resetTimeout)
            {
                throw new Exception("Circuit breaker is open.");
            }

            try
            {
                await operation();
                _failureCount = 0; // Reset on success
            }
            catch (Exception)
            {
                _failureCount++;
                _lastFailureTime = DateTime.UtcNow;
                throw; // Re-throw the exception to be handled by the caller
            }
        }
    }
}
